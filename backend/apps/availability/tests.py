import concurrent.futures
from datetime import date, datetime, timedelta, timezone
from django.test import TransactionTestCase
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, UserRole, OwnerProfile
from apps.accounts.authentication import JWTTokenService
from apps.halls.models import Hall, HallApprovalStatus, HallStatus
from apps.availability.models import HallSlotAvailability, TimeSlot, SlotStatus
from apps.availability.services.availability import AvailabilityService, AvailabilityConflictError

class AvailabilityIntegrationTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Owner
        self.owner = User.objects.create_user(
            email="owner_avail@example.com",
            password="Password123!",
            full_name="Venkat Reddy",
            role=UserRole.OWNER
        )
        OwnerProfile.objects.create(user=self.owner, business_name="Reddy Banquets", city="Hyderabad")
        self.owner_token = JWTTokenService.generate_tokens_for_user(self.owner)['access_token']

        # Hall
        self.hall = Hall.objects.create(
            owner=self.owner,
            name="Orchid Convention Hall",
            address_line1="Road 10",
            city="Hyderabad",
            locality="Madhapur",
            min_capacity=100,
            max_capacity=500,
            base_price_morning=30000,
            base_price_evening=45000,
            base_price_full_day=70000,
            approval_status=HallApprovalStatus.APPROVED,
            status=HallStatus.ACTIVE
        )

    def test_month_availability_matrix_retrieval(self):
        res = self.client.get(f'/api/v1/halls/{self.hall.id}/availability/?year=2026&month=8')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['success'])
        calendar_data = res.data['data']['calendar']
        self.assertIn("2026-08-01", calendar_data)
        self.assertIn("MORNING", calendar_data["2026-08-01"])
        self.assertEqual(calendar_data["2026-08-01"]["MORNING"]["status"], "OPEN")

    def test_check_availability_and_server_price_quote(self):
        payload = {
            "date": "2026-08-15",
            "slot": "EVENING",
            "guest_count": 300,
            "has_catering": True,
            "catering_type": "VEG",
            "has_decor": True,
            "has_dj": True
        }
        res = self.client.post(f'/api/v1/halls/{self.hall.id}/availability/check/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['data']['is_available'])
        quote = res.data['data']['quotation']
        self.assertEqual(quote['hall_rent'], 45000.0)
        self.assertEqual(quote['catering_amount'], 150000.0) # 300 * 500
        self.assertEqual(quote['decor_amount'], 15000.0)
        self.assertEqual(quote['dj_amount'], 10000.0)
        self.assertEqual(quote['subtotal'], 220000.0)
        self.assertEqual(quote['tax_amount'], 39600.0) # 18% of 220k
        self.assertEqual(quote['total_amount'], 259600.0)
        self.assertEqual(quote['advance_amount'], 51920.0) # 20% of 259.6k

    def test_slot_mutual_exclusivity_full_day_blocks_morning_and_evening(self):
        target_date = date(2026, 8, 20)
        
        # Confirm Full Day is booked
        AvailabilityService.confirm_slot_booked(self.hall, target_date, TimeSlot.FULL_DAY, booking_id=None)

        # Checking Morning slot should now be UNAVAILABLE
        morning_check = AvailabilityService.check_availability(self.hall, target_date, TimeSlot.MORNING)
        self.assertFalse(morning_check['is_available'])
        self.assertEqual(morning_check['status'], SlotStatus.BOOKED)

        # Checking Evening slot should now be UNAVAILABLE
        evening_check = AvailabilityService.check_availability(self.hall, target_date, TimeSlot.EVENING)
        self.assertFalse(evening_check['is_available'])
        self.assertEqual(evening_check['status'], SlotStatus.BOOKED)

    def test_slot_mutual_exclusivity_morning_blocks_full_day(self):
        target_date = date(2026, 8, 22)
        
        # Confirm Morning is booked
        AvailabilityService.confirm_slot_booked(self.hall, target_date, TimeSlot.MORNING, booking_id=None)

        # Checking Full Day slot should now be UNAVAILABLE
        full_day_check = AvailabilityService.check_availability(self.hall, target_date, TimeSlot.FULL_DAY)
        self.assertFalse(full_day_check['is_available'])

        # But Evening slot is STILL AVAILABLE!
        evening_check = AvailabilityService.check_availability(self.hall, target_date, TimeSlot.EVENING)
        self.assertTrue(evening_check['is_available'])

    def test_owner_block_and_unblock_manual(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_token}")
        block_payload = {
            "date": "2026-08-25",
            "slot": "EVENING",
            "reason": "Owner family wedding"
        }
        res_block = self.client.post(f'/api/v1/halls/{self.hall.id}/availability/block/', block_payload, format='json')
        self.assertEqual(res_block.status_code, status.HTTP_200_OK)

        # Check availability should now be False
        check_res = AvailabilityService.check_availability(self.hall, date(2026, 8, 25), TimeSlot.EVENING)
        self.assertFalse(check_res['is_available'])
        self.assertEqual(check_res['status'], SlotStatus.BLOCKED)

        # Unblock
        res_unblock = self.client.post(f'/api/v1/halls/{self.hall.id}/availability/unblock/', {
            "date": "2026-08-25",
            "slot": "EVENING"
        }, format='json')
        self.assertEqual(res_unblock.status_code, status.HTTP_200_OK)

        # Check availability is now True
        check_unblocked = AvailabilityService.check_availability(self.hall, date(2026, 8, 25), TimeSlot.EVENING)
        self.assertTrue(check_unblocked['is_available'])

    def test_concurrent_slot_holds_prevent_double_booking(self):
        """
        Simulates multi-threaded concurrent hold requests for the same hall/date/slot.
        Exactly ONE thread must succeed and all other threads must receive Conflict.
        """
        from django.db import connections
        target_date = date(2026, 8, 28)
        target_slot = TimeSlot.EVENING

        # Pre-seed the slot so concurrent transactions only contend on row lock / update
        HallSlotAvailability.objects.get_or_create(
            hall=self.hall,
            date=target_date,
            slot=target_slot,
            defaults={'status': SlotStatus.OPEN}
        )

        def try_hold_slot(customer_idx):
            import uuid
            try:
                AvailabilityService.hold_slot_atomic(
                    hall=self.hall,
                    event_date=target_date,
                    slot=target_slot,
                    booking_id=uuid.uuid4(),
                    duration_minutes=15
                )
                return "SUCCESS"
            except AvailabilityConflictError:
                return "CONFLICT"
            finally:
                connections.close_all()

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(try_hold_slot, i) for i in range(5)]
            results = [f.result() for f in futures]

        connections.close_all()
        success_count = results.count("SUCCESS")
        conflict_count = results.count("CONFLICT")

        self.assertEqual(success_count, 1, f"Expected exactly 1 success, got {success_count}")
        self.assertEqual(conflict_count, 4, f"Expected 4 conflicts, got {conflict_count}")
