from decimal import Decimal
from datetime import date, datetime, timedelta, timezone
from django.test import TestCase
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, UserRole, OwnerProfile
from apps.accounts.authentication import JWTTokenService
from apps.halls.models import Hall, HallApprovalStatus, HallStatus, CancellationPolicy
from apps.availability.models import TimeSlot, SlotStatus, HallSlotAvailability
from apps.bookings.models import Booking, BookingStatus, EventType
from apps.bookings.services.pricing import PricingService
from apps.bookings.services.booking import BookingService

class BookingDomainTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Owner
        self.owner = User.objects.create_user(
            email="owner_bk@example.com",
            password="Password123!",
            full_name="K. Rao",
            role=UserRole.OWNER
        )
        OwnerProfile.objects.create(user=self.owner, business_name="Rao Conventions", city="Hyderabad")
        self.owner_token = JWTTokenService.generate_tokens_for_user(self.owner)['access_token']

        # Customer 1
        self.customer1 = User.objects.create_user(
            email="cust1@example.com",
            password="Password123!",
            full_name="Rahul Sharma",
            role=UserRole.CUSTOMER,
            phone="+919876540001"
        )
        self.cust1_token = JWTTokenService.generate_tokens_for_user(self.customer1)['access_token']

        # Customer 2
        self.customer2 = User.objects.create_user(
            email="cust2@example.com",
            password="Password123!",
            full_name="Amit Patel",
            role=UserRole.CUSTOMER,
            phone="+919876540002"
        )
        self.cust2_token = JWTTokenService.generate_tokens_for_user(self.customer2)['access_token']

        # Hall
        self.hall = Hall.objects.create(
            owner=self.owner,
            name="Grand Orchid Conventions",
            address_line1="Road 36, Madhapur",
            city="Hyderabad",
            locality="Madhapur",
            min_capacity=150,
            max_capacity=600,
            base_price_morning=35000,
            base_price_evening=50000,
            base_price_full_day=80000,
            advance_percentage=20,
            veg_plate_price=500,
            non_veg_plate_price=750,
            decor_price=15000,
            dj_price=10000,
            cancellation_policy=CancellationPolicy.FLEXIBLE,
            approval_status=HallApprovalStatus.APPROVED,
            status=HallStatus.ACTIVE
        )

    def test_pricing_service_decimal_calculation(self):
        quote = PricingService.calculate_quote(
            hall=self.hall,
            slot=TimeSlot.EVENING,
            guest_count=350,
            has_catering=True,
            catering_type='VEG',
            has_decor=True,
            has_dj=True
        )
        # Rent: 50,000
        # Catering: 350 * 500 = 175,000
        # Decor: 15,000
        # DJ: 10,000
        # Subtotal: 250,000
        # Tax 18%: 45,000
        # Total: 295,000
        # Advance 20%: 59,000
        # Balance 80%: 236,000
        self.assertEqual(quote['hall_rent'], Decimal('50000.00'))
        self.assertEqual(quote['catering_amount'], Decimal('175000.00'))
        self.assertEqual(quote['subtotal'], Decimal('250000.00'))
        self.assertEqual(quote['tax_amount'], Decimal('45000.00'))
        self.assertEqual(quote['total_amount'], Decimal('295000.00'))
        self.assertEqual(quote['advance_amount'], Decimal('59000.00'))
        self.assertEqual(quote['balance_amount'], Decimal('236000.00'))

    def test_create_booking_intent_success_and_slot_hold(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.cust1_token}")
        event_date = date.today() + timedelta(days=5)
        payload = {
            "hall_id": str(self.hall.id),
            "event_type": "WEDDING",
            "event_date": event_date.isoformat(),
            "time_slot": "EVENING",
            "guest_count": 350,
            "contact_name": "Rahul Sharma",
            "contact_phone": "+919876540001",
            "has_catering": True,
            "catering_type": "VEG",
            "has_decor": True,
            "has_dj": True
        }
        res = self.client.post('/api/v1/bookings/create-intent/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['success'])
        booking_data = res.data['data']
        self.assertEqual(booking_data['status'], "PAYMENT_PENDING")
        self.assertEqual(Decimal(str(booking_data['total_amount'])), Decimal('295000.00'))

        # Slot should now be HELD in availability table
        slot_rec = HallSlotAvailability.objects.get(hall=self.hall, date=event_date.isoformat(), slot=TimeSlot.EVENING)
        self.assertEqual(slot_rec.status, SlotStatus.HELD)
        self.assertTrue(slot_rec.is_currently_held)

    def test_create_booking_intent_without_event_type_is_allowed(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.cust1_token}")
        event_date = date.today() + timedelta(days=5)
        payload = {
            "hall_id": str(self.hall.id),
            "event_date": event_date.isoformat(),
            "time_slot": "EVENING",
            "guest_count": 350,
            "contact_name": "Rahul Sharma",
            "contact_phone": "+919876540001",
            "has_catering": True,
            "catering_type": "VEG",
            "has_decor": True,
            "has_dj": True,
        }
        res = self.client.post('/api/v1/bookings/create-intent/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['success'])

    def test_booking_intent_rejects_dates_less_than_one_day_in_advance(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.cust1_token}")
        today = date.today()
        too_soon = today + timedelta(days=0)
        payload = {
            "hall_id": str(self.hall.id),
            "event_type": "WEDDING",
            "event_date": too_soon.isoformat(),
            "time_slot": "EVENING",
            "guest_count": 350,
            "contact_name": "Rahul Sharma",
            "contact_phone": "+919876540001",
            "has_catering": True,
            "catering_type": "VEG",
            "has_decor": True,
            "has_dj": True,
        }
        res = self.client.post('/api/v1/bookings/create-intent/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(res.data['success'])
        self.assertEqual('Bookings must be made at least 1 day(s) in advance.', res.data['message'])
        self.assertIn('Bookings must be made at least 1 day(s) in advance.', res.data['errors']['event_date'][0])

    def test_booking_intent_reuse_on_repeat_checkout(self):
        """Re-submitting checkout for the same user/slot updates the existing intent rather than creating duplicates."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.cust1_token}")
        booking_date = date.today() + timedelta(days=12)
        payload_1 = {
            "hall_id": str(self.hall.id),
            "event_type": "WEDDING",
            "event_date": booking_date.isoformat(),
            "time_slot": "EVENING",
            "guest_count": 300,
            "contact_name": "Rahul",
            "contact_phone": "+919876540001",
        }
        res_1 = self.client.post('/api/v1/bookings/create-intent/', payload_1, format='json')
        self.assertEqual(res_1.status_code, status.HTTP_201_CREATED)
        booking_id_1 = res_1.data['data']['id']

        # Customer changes guest count to 400 and clicks proceed again
        payload_2 = {
            "hall_id": str(self.hall.id),
            "event_type": "WEDDING",
            "event_date": booking_date.isoformat(),
            "time_slot": "EVENING",
            "guest_count": 400,
            "contact_name": "Rahul Sharma",
            "contact_phone": "+919876540001",
        }
        res_2 = self.client.post('/api/v1/bookings/create-intent/', payload_2, format='json')
        self.assertEqual(res_2.status_code, status.HTTP_201_CREATED)
        booking_id_2 = res_2.data['data']['id']

        # ID should be identical (reused and updated in place)
        self.assertEqual(booking_id_1, booking_id_2)
        self.assertEqual(Booking.objects.filter(customer=self.customer1, event_date=booking_date).count(), 1)

        updated_booking = Booking.objects.get(id=booking_id_1)
        self.assertEqual(updated_booking.guest_count, 400)

    def test_second_customer_booking_same_slot_is_blocked(self):
        blocked_date = date.today() + timedelta(days=14)

        # Customer 1 creates booking intent
        BookingService.create_booking_intent(
            customer=self.customer1,
            hall=self.hall,
            event_type=EventType.WEDDING,
            event_date=blocked_date,
            time_slot=TimeSlot.EVENING,
            guest_count=300,
            contact_name="Rahul",
            contact_phone="+919876540001"
        )

        # Customer 2 attempts to create booking intent for same date and slot
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.cust2_token}")
        payload = {
            "hall_id": str(self.hall.id),
            "event_type": "RECEPTION",
            "event_date": blocked_date.isoformat(),
            "time_slot": "EVENING",
            "guest_count": 250,
            "contact_name": "Amit Patel",
            "contact_phone": "+919876540002"
        }
        res = self.client.post('/api/v1/bookings/create-intent/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(res.data['success'])

    def test_idor_customer_cannot_view_other_customer_booking(self):
        booking = BookingService.create_booking_intent(
            customer=self.customer1,
            hall=self.hall,
            event_type=EventType.WEDDING,
            event_date=date.today() + timedelta(days=16),
            time_slot=TimeSlot.MORNING,
            guest_count=200,
            contact_name="Rahul",
            contact_phone="+919876540001"
        )

        # Customer 2 tries to access Customer 1's booking
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.cust2_token}")
        res = self.client.get(f'/api/v1/bookings/{booking.id}/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_accept_and_reject_workflows(self):
        booking = BookingService.create_booking_intent(
            customer=self.customer1,
            hall=self.hall,
            event_type=EventType.WEDDING,
            event_date=date.today() + timedelta(days=20),
            time_slot=TimeSlot.EVENING,
            guest_count=300,
            contact_name="Rahul",
            contact_phone="+919876540001"
        )
        # Advance payment simulated
        booking.status = BookingStatus.PENDING_OWNER_CONFIRMATION
        booking.amount_paid = booking.advance_amount
        booking.save()

        # Owner accepts
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_token}")
        accept_res = self.client.post(f'/api/v1/bookings/{booking.id}/accept/', {"notes": "Looking forward to hosting your wedding!"}, format='json')
        self.assertEqual(accept_res.status_code, status.HTTP_200_OK)
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.CONFIRMED)
        self.assertEqual(booking.owner_response_notes, "Looking forward to hosting your wedding!")

        # Slot should now be BOOKED
        slot_rec = HallSlotAvailability.objects.get(hall=self.hall, date=booking.event_date.isoformat(), slot=TimeSlot.EVENING)
        self.assertEqual(slot_rec.status, SlotStatus.BOOKED)

    def test_customer_refund_windows_apply_automatically(self):
        """Customer cancellations should follow the 90/50/0% window rule."""
        base_hall = Hall.objects.create(
            owner=self.owner,
            name="Refund Window Venue",
            address_line1="Road 2",
            city="Hyderabad",
            locality="Kondapur",
            cancellation_policy=CancellationPolicy.MODERATE,
            approval_status=HallApprovalStatus.APPROVED,
            status=HallStatus.ACTIVE
        )

        far_booking = Booking.objects.create(
            customer=self.customer1,
            hall=base_hall,
            event_type=EventType.WEDDING,
            event_date=date.today() + timedelta(days=120),
            time_slot=TimeSlot.EVENING,
            guest_count=200,
            contact_name="Rahul",
            contact_phone="+919876540001",
            hall_rent=45000,
            subtotal=45000,
            tax_amount=8100,
            total_amount=53100,
            advance_amount=10620,
            balance_amount=42480,
            amount_paid=10620,
            status=BookingStatus.CONFIRMED
        )
        far_cancelled = BookingService.cancel_booking(far_booking, self.customer1, reason="Booked too early")
        self.assertEqual(far_cancelled.refund_amount, Decimal('9540.00'))

        mid_booking = Booking.objects.create(
            customer=self.customer1,
            hall=base_hall,
            event_type=EventType.WEDDING,
            event_date=date.today() + timedelta(days=45),
            time_slot=TimeSlot.MORNING,
            guest_count=200,
            contact_name="Rahul",
            contact_phone="+919876540001",
            hall_rent=45000,
            subtotal=45000,
            tax_amount=8100,
            total_amount=53100,
            advance_amount=10620,
            balance_amount=42480,
            amount_paid=10620,
            status=BookingStatus.CONFIRMED
        )
        mid_cancelled = BookingService.cancel_booking(mid_booking, self.customer1, reason="Change of plans")
        self.assertEqual(mid_cancelled.refund_amount, Decimal('5310.00'))

        near_booking = Booking.objects.create(
            customer=self.customer1,
            hall=base_hall,
            event_type=EventType.WEDDING,
            event_date=date.today() + timedelta(days=10),
            time_slot=TimeSlot.EVENING,
            guest_count=200,
            contact_name="Rahul",
            contact_phone="+919876540001",
            hall_rent=45000,
            subtotal=45000,
            tax_amount=8100,
            total_amount=53100,
            advance_amount=10620,
            balance_amount=42480,
            amount_paid=10620,
            status=BookingStatus.CONFIRMED
        )
        near_cancelled = BookingService.cancel_booking(near_booking, self.customer1, reason="Very late change")
        self.assertEqual(near_cancelled.refund_amount, Decimal('0.00'))
        self.assertEqual(near_cancelled.cancellation_fee, Decimal('10620.00'))

    def test_strict_cancellation_policy_refund_calculation(self):
        """Under STRICT policy, cancellations closer than 30 days receive 0% refund."""
        strict_hall = Hall.objects.create(
            owner=self.owner,
            name="Strict Cancellation Venue",
            address_line1="Road 1",
            city="Hyderabad",
            locality="Madhapur",
            cancellation_policy=CancellationPolicy.STRICT,
            approval_status=HallApprovalStatus.APPROVED,
            status=HallStatus.ACTIVE
        )
        near_booking = Booking.objects.create(
            customer=self.customer1,
            hall=strict_hall,
            event_type=EventType.WEDDING,
            event_date=date.today() + timedelta(days=10), # Only 10 days away!
            time_slot=TimeSlot.EVENING,
            guest_count=200,
            contact_name="Rahul",
            contact_phone="+919876540001",
            hall_rent=45000,
            subtotal=45000,
            tax_amount=8100,
            total_amount=53100,
            advance_amount=10620,
            balance_amount=42480,
            amount_paid=10620,
            status=BookingStatus.CONFIRMED
        )

        cancelled = BookingService.cancel_booking(near_booking, self.customer1, reason="Change of plans")
        self.assertEqual(cancelled.status, BookingStatus.CANCELLED_BY_CUSTOMER)
        self.assertEqual(cancelled.refund_amount, Decimal('0.00'))
        self.assertEqual(cancelled.cancellation_fee, Decimal('10620.00'))

    def test_owner_refund_must_be_processed_within_24_hours(self):
        booking = BookingService.create_booking_intent(
            customer=self.customer1,
            hall=self.hall,
            event_type=EventType.WEDDING,
            event_date=date.today() + timedelta(days=35),
            time_slot=TimeSlot.EVENING,
            guest_count=250,
            contact_name="Rahul",
            contact_phone="+919876540001"
        )
        booking.amount_paid = booking.advance_amount
        booking.status = BookingStatus.CONFIRMED
        booking.save(update_fields=['amount_paid', 'status'])

        cancelled_booking = BookingService.cancel_booking(booking, self.customer1, reason="Plans changed")
        cancelled_booking.updated_at = timezone.now() - timedelta(days=2)
        cancelled_booking.save(update_fields=['updated_at'])

        with self.assertRaisesMessage(Exception, 'Refunds for customer cancellations must be processed within 24 hours.'):
            BookingService.process_booking_refund(
                cancelled_booking,
                self.owner,
                reason='Late refund',
                amount=cancelled_booking.refund_amount,
            )
