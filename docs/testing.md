# Testing Strategy & Quality Assurance Plan

## 1. Test Pyramid & Quality Gates

The HallBook test suite enforces zero-tolerance for concurrency flaws, pricing drift, unauthorized data access, and state-machine violations:

```
                  ┌─────────────────┐
                  │    E2E Tests    │   (Critical User Journeys)
                  │  (Playwright)   │
                  ├─────────────────┤
                  │Integration Tests│   (APIs, Webhooks, DB Transactions)
                  │  (Pytest/Django)│
                  ├─────────────────┤
                  │   Unit Tests    │   (PricingService, State Machines,
                  │  (Pytest/DRF)   │    Commission, Time Slot Exclusivity)
                  └─────────────────┘
```

---

## 2. Unit Testing Scope

1. **`PricingServiceTests`**:
   - Base rent calculations for Morning vs Evening vs Full Day.
   - Per-plate catering calculations with Veg vs Non-Veg pricing.
   - Add-on fees (Decor, DJ) calculations.
   - GST tax rounding using `Decimal('0.01')` quantize.
   - Advance (20%) and balance (80%) exact breakdown matching total.
2. **`BookingStateMachineTests`**:
   - Valid state progression (`PAYMENT_PENDING` -> `PENDING_OWNER_CONFIRMATION` -> `CONFIRMED` -> `COMPLETED`).
   - Rejection of invalid transitions (e.g. attempting to skip payment or review uncompleted bookings).
3. **`CommissionCalculationTests`**:
   - Correct deduction of 10% platform commission and TDS/GST components.

---

## 3. Concurrency & Race-Condition Testing

A dedicated test suite simulates multi-threaded simultaneous booking requests for the same hall and date:

```python
# apps/bookings/tests/test_concurrency.py
import concurrent.futures
from django.test import TransactionTestCase
from apps.bookings.services.booking import BookingService

class BookingConcurrencyTests(TransactionTestCase):
    def test_simultaneous_booking_attempts_prevent_double_booking(self):
        hall = create_test_hall()
        date = "2026-09-15"
        slot = "EVENING"

        def attempt_booking(customer):
            return BookingService.create_booking_intent(
                customer=customer,
                hall_id=hall.id,
                event_date=date,
                slot=slot,
                guest_count=200
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(attempt_booking, user) for user in test_users]
            results = [f.result() for f in futures]

        successful_bookings = [r for r in results if r['success'] is True]
        conflicted_bookings = [r for r in results if r['success'] is False and r['code'] == 'SLOT_UNAVAILABLE']

        self.assertEqual(len(successful_bookings), 1)
        self.assertEqual(len(conflicted_bookings), 4)
```

---

## 4. Security & Access Control Tests

1. **IDOR Prevention Tests**:
   - Customer A attempting to retrieve `/api/v1/bookings/{id_of_customer_b}/` returns HTTP 403 Forbidden.
   - Owner A attempting to modify `/api/v1/halls/{id_of_owner_b}/` returns HTTP 403 Forbidden.
2. **Role Escalation Tests**:
   - Customer attempting to access `/api/v1/admin/owners/` returns HTTP 403.
3. **Webhook Cryptographic Tests**:
   - Forged signature payload returns HTTP 400 Bad Request.
