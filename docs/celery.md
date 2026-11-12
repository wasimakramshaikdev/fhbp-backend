# Celery Background Processing & Scheduled Tasks

## 1. Queue Architecture & Worker Pools

HallBook utilizes **Redis 7** as the Celery broker and result backend. Tasks are routed into dedicated queues based on priority and latency requirements:

```
[ Django Web API ]
       │
       ├── (Low Latency / Financial) ──────> [ Queue: payments ] ─────> Worker Pool 1
       │   - process_payout
       │   - execute_refund
       │
       ├── (Customer Facing / Critical) ───> [ Queue: emails ] ───────> Worker Pool 2
       │   - send_booking_confirmation
       │   - send_owner_booking_alert
       │   - send_password_reset_email
       │
       ├── (Heavy / Asynchronous) ─────────> [ Queue: media ] ────────> Worker Pool 3
       │   - process_hall_images
       │   - generate_pdf_invoice
       │
       └── (Periodic / Maintenance) ───────> [ Queue: beat_tasks ] ───> Worker Pool 4
           - expire_unpaid_holds
           - send_balance_reminders
           - auto_complete_past_events
```

---

## 2. Inventory of Celery Tasks

| Task Name | Queue | Retry Policy | Description |
|---|---|---|---|
| `send_email_notification` | `emails` | Max 5 retries, Exponential Backoff (30s, 60s, 120s, 300s) | Sends transactional emails via SMTP/SES |
| `send_in_app_notification` | `emails` | Max 3 retries, Linear Backoff (10s) | Writes unread alert to user notification feed |
| `generate_booking_invoice` | `media` | Max 3 retries | Generates compliant PDF receipt & stores S3 key |
| `process_uploaded_image` | `media` | Max 2 retries | Optimizes image resolution, creates thumbnails, validates EXIF |
| `expire_pending_bookings` | `beat_tasks` | Idempotent, No retry | Scans bookings with `status=PAYMENT_PENDING` older than 15 mins and frees slots |
| `process_scheduled_payouts`| `payouts` | Max 3 retries with lock guard | Dispatches pending owner payouts for completed events past dispute window |
| `send_balance_due_reminders`| `emails`| Idempotent, No retry | Notifies customers 7 days & 2 days prior to event date if balance remains |
| `auto_complete_past_events`| `beat_tasks` | Idempotent | Transitions bookings to `COMPLETED` when event date + slot concludes |

---

## 3. Task Idempotency Design

To prevent duplicate emails or duplicate financial transactions during network failures or worker retries:

```python
# apps/core/tasks.py
from celery import shared_task
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_payout_task(self, payout_id: str):
    lock_key = f"lock:payout:{payout_id}"
    # Acquire Redis distributed lock for 10 minutes
    acquired = cache.add(lock_key, "locked", timeout=600)
    if not acquired:
        logger.warning(f"Payout {payout_id} is currently being processed by another worker.")
        return

    try:
        from apps.payouts.services.payout import PayoutService
        PayoutService.execute_payout(payout_id)
    except Exception as exc:
        logger.error(f"Error processing payout {payout_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc)
    finally:
        cache.delete(lock_key)
```

---

## 4. Celery Beat Schedule Configuration

```python
# config/celery.py
CELERY_BEAT_SCHEDULE = {
    'expire-unpaid-booking-holds': {
        'task': 'apps.bookings.tasks.expire_unpaid_holds',
        'schedule': 60.0, # Every 60 seconds
    },
    'auto-complete-events-and-enable-reviews': {
        'task': 'apps.bookings.tasks.auto_complete_past_events',
        'schedule': 3600.0, # Every 1 hour
    },
    'send-upcoming-event-balance-reminders': {
        'task': 'apps.notifications.tasks.send_balance_reminders',
        'schedule': 86400.0, # Daily at 09:00 AM UTC
    },
    'payout-eligibility-sweep': {
        'task': 'apps.payouts.tasks.process_eligible_payouts',
        'schedule': 86400.0, # Daily at midnight
    },
}
```
