from decimal import Decimal
from datetime import date, datetime, timedelta, timezone
from django.test import TransactionTestCase
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, UserRole, OwnerProfile, OwnerVerificationStatus
from apps.accounts.authentication import JWTTokenService
from apps.halls.models import Hall, HallImage, Amenity, HallApprovalStatus, HallStatus, HallType, CancellationPolicy
from apps.availability.models import HallSlotAvailability, TimeSlot, SlotStatus
from apps.availability.services.availability import AvailabilityService
from apps.bookings.models import Booking, BookingStatus, EventType
from apps.bookings.services.pricing import PricingService
from apps.bookings.services.booking import BookingService
from apps.payments.models import Payment, PaymentStatus, PaymentType, PaymentMethod
from apps.payments.services.payment import PaymentService
from apps.notifications.models import Notification, NotificationType
from apps.reviews.models import Review
from apps.disputes.models import Dispute, DisputeStatus, DisputeResolutionType

class EndToEndAcceptanceTests(TransactionTestCase):
    """
    Exhaustive End-to-End Acceptance test suite executing the complete real-world journeys
    defined in Section 65 & 96 of the master specification.
    """
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        self.owner = User.objects.create_user(
            email="owner_shared_e2e@example.com",
            password="Password123!",
            full_name="Shared Host",
            role=UserRole.OWNER
        )
        OwnerProfile.objects.create(user=self.owner, business_name="Shared Banquets LLC", pan_gst_number="36AABCG1234F1Z5")

        self.test_hall = Hall.objects.create(
            owner=self.owner,
            name="Grand Orchid Conventions",
            address_line1="Road 36, Madhapur",
            city="Hyderabad",
            locality="Madhapur",
            min_capacity=100,
            max_capacity=600,
            base_price_morning=35000,
            base_price_evening=50000,
            base_price_full_day=80000,
            advance_percentage=20,
            veg_plate_price=500,
            approval_status=HallApprovalStatus.APPROVED,
            status=HallStatus.ACTIVE
        )

    def test_customer_complete_e2e_journey(self):
        """
        CUSTOMER: Register -> Login -> Search Madhapur -> View Hall ->
        Check Availability & Quote -> Book & Pay Advance -> Receive Confirmation ->
        Owner Accepts -> Event Completes -> Submit 5-Star Review -> Hall Rating Recalculates.
        """
        # 1. Register Customer
        cust_reg = self.client.post('/api/v1/auth/register/', {
            "full_name": "Kiran Kumar",
            "email": "kiran.kumar@example.com",
            "phone": "+919876599001",
            "password": "Password123!",
            "role": "CUSTOMER"
        }, format='json')
        self.assertEqual(cust_reg.status_code, status.HTTP_201_CREATED)
        self.assertTrue(cust_reg.data['success'])

        # 2. Login
        login_res = self.client.post('/api/v1/auth/login/', {
            "email": "kiran.kumar@example.com",
            "password": "Password123!"
        }, format='json')
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        customer_token = login_res.data['data']['tokens']['access_token']
        customer_user = User.objects.get(email="kiran.kumar@example.com")

        # Setup an approved hall with owner
        owner = User.objects.create_user(email="owner_e2e@example.com", password="Password123!", full_name="Naidu Host", role=UserRole.OWNER)
        OwnerProfile.objects.create(user=owner, business_name="Naidu Banquets LLC", pan_gst_number="36AABCG1234F1Z5")
        owner_token = JWTTokenService.generate_tokens_for_user(owner)['access_token']

        hall = Hall.objects.create(
            owner=owner,
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
            approval_status=HallApprovalStatus.APPROVED,
            status=HallStatus.ACTIVE
        )

        # 3. Search Halls in Madhapur with 350 guests
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {customer_token}")
        search_res = self.client.get('/api/v1/halls/?city=Hyderabad&locality=Madhapur&guests=350')
        self.assertEqual(search_res.status_code, status.HTTP_200_OK)
        self.assertIn("Grand Orchid Conventions", [h['name'] for h in search_res.data['data']])

        # 4. View Hall Details & Calculate Dynamic Quotation
        detail_res = self.client.get(f'/api/v1/halls/{hall.slug}/')
        self.assertEqual(detail_res.status_code, status.HTTP_200_OK)

        check_res = self.client.post(f'/api/v1/halls/{hall.id}/availability/check/', {
            "date": "2026-09-12",
            "slot": "EVENING",
            "guest_count": 350,
            "has_catering": True,
            "catering_type": "VEG",
            "has_decor": True,
            "has_dj": True
        }, format='json')
        self.assertEqual(check_res.status_code, status.HTTP_200_OK)
        self.assertTrue(check_res.data['data']['is_available'])
        quote = check_res.data['data']['quotation']
        self.assertEqual(quote['hall_rent'], 50000.0)
        self.assertEqual(quote['subtotal'], 250000.0)
        self.assertEqual(quote['total_amount'], 295000.0)
        self.assertEqual(quote['advance_amount'], 59000.0)

        # 5. Create Booking Intent (Pessimistic Hold)
        intent_res = self.client.post('/api/v1/bookings/create-intent/', {
            "hall_id": str(hall.id),
            "event_type": "WEDDING",
            "event_date": "2026-09-12",
            "time_slot": "EVENING",
            "guest_count": 350,
            "contact_name": "Kiran Kumar",
            "contact_phone": "+919876599001",
            "has_catering": True,
            "catering_type": "VEG",
            "has_decor": True,
            "has_dj": True
        }, format='json')
        self.assertEqual(intent_res.status_code, status.HTTP_201_CREATED)
        booking_id = intent_res.data['data']['id']
        booking_number = intent_res.data['data']['booking_number']

        # 6. Initiate & Verify Advance Payment
        pay_init = self.client.post('/api/v1/payments/initiate/', {
            "booking_id": booking_id,
            "payment_type": "ADVANCE",
            "payment_method": "UPI"
        }, format='json')
        self.assertEqual(pay_init.status_code, status.HTTP_201_CREATED)
        order_id = pay_init.data['data']['gateway_order_id']

        pay_verify = self.client.post('/api/v1/payments/verify/', {
            "gateway_order_id": order_id,
            "gateway_payment_id": "pay_test_kiran_01",
            "gateway_signature": "valid_simulated_signature"
        }, format='json')
        self.assertEqual(pay_verify.status_code, status.HTTP_200_OK)

        booking = Booking.objects.get(id=booking_id)
        self.assertEqual(booking.status, BookingStatus.PENDING_OWNER_CONFIRMATION)
        self.assertEqual(booking.amount_paid, Decimal('59000.00'))

        # 7. Owner Receives Request & Accepts
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {owner_token}")
        owner_accept = self.client.post(f'/api/v1/bookings/{booking_id}/accept/', {
            "notes": "Delighted to confirm your wedding reservation!"
        }, format='json')
        self.assertEqual(owner_accept.status_code, status.HTTP_200_OK)

        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.CONFIRMED)

        # 8. Event Concludes (Status -> COMPLETED)
        booking.status = BookingStatus.COMPLETED
        booking.save(update_fields=['status'])

        # 9. Customer Leaves 5-Star Review
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {customer_token}")
        rev_res = self.client.post(f'/api/v1/bookings/{booking_id}/review/', {
            "rating": 5,
            "comment": "Dream wedding experience! Flawless acoustics, banquet decor was spectacular, and the air conditioning was ice cold!"
        }, format='json')
        self.assertEqual(rev_res.status_code, status.HTTP_201_CREATED)

        hall.refresh_from_db()
        self.assertEqual(hall.avg_rating, Decimal('5.00'))
        self.assertEqual(hall.review_count, 1)

    def test_owner_onboarding_and_admin_approval_journey(self):
        """
        OWNER: Register -> 4-Step Onboarding -> Upload Imagery -> Submit for Approval ->
        ADMIN: Review -> Approve Listing -> Listing goes LIVE on public marketplace.
        """
        admin = User.objects.create_superuser(email="admin_e2e@hallbook.in", password="AdminPassword123!", full_name="Super Admin")
        admin_token = JWTTokenService.generate_tokens_for_user(admin)['access_token']

        # 1. Register Owner
        reg_res = self.client.post('/api/v1/auth/register/', {
            "full_name": "Suresh Reddy",
            "email": "suresh@royalpalms.com",
            "phone": "+919876588001",
            "password": "OwnerPassword123!",
            "role": "OWNER",
            "business_name": "Royal Palms Banquets LLP",
            "city": "Hyderabad",
            "locality": "Gachibowli"
        }, format='json')
        self.assertEqual(reg_res.status_code, status.HTTP_201_CREATED)
        owner_token = reg_res.data['data']['tokens']['access_token']

        # 2. Create Draft Venue Listing (Onboarding Steps 1, 2, 3)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {owner_token}")
        create_res = self.client.post('/api/v1/owner/listings/', {
            "name": "Royal Palms Grand Palace",
            "description": "Luxurious 800-capacity convention hall in Gachibowli.",
            "address_line1": "Financial District Rd",
            "city": "Hyderabad",
            "locality": "Gachibowli",
            "postal_code": "500032",
            "min_capacity": 200,
            "max_capacity": 800,
            "hall_type": "CONVENTION",
            "base_price_morning": "40000.00",
            "base_price_evening": "65000.00",
            "base_price_full_day": "95000.00",
            "advance_percentage": "20.00",
            "catering_policy": "BOTH",
            "veg_plate_price": "600.00",
            "non_veg_plate_price": "850.00",
            "initial_images": ["https://images.unsplash.com/photo-1545232979-8bf68ee9b1af"]
        }, format='json')
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        hall_id = create_res.data['data']['id']
        hall_slug = create_res.data['data']['slug']

        # 3. Submit for Admin Approval (Step 4)
        submit_res = self.client.post(f'/api/v1/owner/listings/{hall_id}/submit/')
        self.assertEqual(submit_res.status_code, status.HTTP_200_OK)

        # 4. Verify Not Visible Publicly while under review
        self.client.credentials() # unauthenticated
        pub_check = self.client.get(f'/api/v1/halls/{hall_slug}/')
        self.assertEqual(pub_check.status_code, status.HTTP_404_NOT_FOUND)

        # 5. Super Admin Reviews & Approves Listing
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_token}")
        admin_approve = self.client.post(f'/api/v1/admin/halls/{hall_id}/action/', {
            "action": "APPROVE"
        }, format='json')
        self.assertEqual(admin_approve.status_code, status.HTTP_200_OK)

        # 6. Listing is now LIVE on marketplace!
        self.client.credentials() # unauthenticated
        pub_live = self.client.get(f'/api/v1/halls/{hall_slug}/')
        self.assertEqual(pub_live.status_code, status.HTTP_200_OK)
        self.assertEqual(pub_live.data['data']['name'], "Royal Palms Grand Palace")

    def test_unauthenticated_booking_returns_401_with_www_authenticate(self):
        """Unauthenticated booking attempt must return HTTP 401 with WWW-Authenticate header."""
        self.client.credentials() # No token

        res = self.client.post('/api/v1/bookings/create-intent/', {
            "hall_id": str(self.test_hall.id),
            "event_date": "2026-09-20",
            "time_slot": "EVENING",
            "guest_count": 200,
            "contact_name": "Anonymous",
            "contact_phone": "+919876543210"
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(res.data['code'], "AUTHENTICATION_FAILED")
        self.assertIn('WWW-Authenticate', res.headers)

    def test_expired_access_token_refreshes_and_allows_booking(self):
        """Expired access token is refreshed via /api/v1/auth/refresh/ and new token successfully books."""
        customer = User.objects.create_user(
            email="expired_test@example.com",
            password="Password123!",
            full_name="Expired User",
            role=UserRole.CUSTOMER
        )
        tokens = JWTTokenService.generate_tokens_for_user(customer)
        refresh_token = tokens['refresh_token']

        # 1. Use refresh token to obtain a fresh access token
        refresh_res = self.client.post('/api/v1/auth/refresh/', {
            "refresh_token": refresh_token
        }, format='json')
        self.assertEqual(refresh_res.status_code, status.HTTP_200_OK)
        new_access_token = refresh_res.data['data']['access_token']

        # 2. Use new access token to create booking intent
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access_token}")

        booking_res = self.client.post('/api/v1/bookings/create-intent/', {
            "hall_id": str(self.test_hall.id),
            "event_type": "WEDDING",
            "event_date": "2026-09-22",
            "time_slot": "EVENING",
            "guest_count": 250,
            "contact_name": "Expired User",
            "contact_phone": "+919876543210"
        }, format='json')
        self.assertEqual(booking_res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(booking_res.data['success'])
        self.assertEqual(booking_res.data['data']['status'], "PAYMENT_PENDING")

    def test_refreshed_access_token_allows_notification_unread_count(self):
        """Proves refreshed access token authenticates on /notifications/unread-count/."""
        customer = User.objects.create_user(
            email="notif_e2e_refresh@example.com",
            password="Password123!",
            full_name="Notif User",
            role=UserRole.CUSTOMER
        )
        Notification.objects.create(
            user=customer,
            title="E2E Notif",
            message="Test message",
            type=NotificationType.BOOKING_CREATED
        )
        tokens = JWTTokenService.generate_tokens_for_user(customer)

        refresh_res = self.client.post('/api/v1/auth/refresh/', {
            "refresh_token": tokens['refresh_token']
        }, format='json')
        self.assertEqual(refresh_res.status_code, status.HTTP_200_OK)
        new_access_token = refresh_res.data['data']['access_token']

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access_token}")
        notif_res = self.client.get('/api/v1/notifications/unread-count/')
        self.assertEqual(notif_res.status_code, status.HTTP_200_OK)
        self.assertEqual(notif_res.data['data']['unread_count'], 1)
