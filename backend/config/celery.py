import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('hallbook')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Explicit queue routing
app.conf.task_routes = {
    'apps.payments.tasks.*': {'queue': 'payments'},
    'apps.payouts.tasks.*': {'queue': 'payments'},
    'apps.notifications.tasks.send_email_notification_task': {'queue': 'emails'},
    'apps.notifications.tasks.send_in_app_notification_task': {'queue': 'emails'},
    'apps.notifications.tasks.send_balance_reminders': {'queue': 'emails'},
    'apps.bookings.tasks.expire_unpaid_holds': {'queue': 'default'},
    'apps.bookings.tasks.auto_complete_past_events': {'queue': 'default'},
}

# Periodic task schedules
app.conf.beat_schedule = {
    'expire-unpaid-booking-holds': {
        'task': 'apps.bookings.tasks.expire_unpaid_holds',
        'schedule': 60.0,  # Every 60 seconds
    },
    'auto-complete-past-events': {
        'task': 'apps.bookings.tasks.auto_complete_past_events',
        'schedule': 3600.0,  # Every 1 hour
    },
    'send-daily-balance-reminders': {
        'task': 'apps.notifications.tasks.send_balance_reminders',
        'schedule': crontab(hour=9, minute=0),  # 09:00 AM UTC
    },
    'payout-eligibility-sweep': {
        'task': 'apps.payouts.tasks.process_eligible_payouts',
        'schedule': crontab(hour=0, minute=0),  # Midnight UTC
    },
}

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
