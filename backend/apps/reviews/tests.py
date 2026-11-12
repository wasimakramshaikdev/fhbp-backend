from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, UserRole, OwnerProfile
from apps.accounts.authentication import JWTTokenService
from apps.halls.models import Hall, HallApprovalStatus, HallStatus
from apps.availability.models import TimeSlot
from apps.bookings.models import Booking, BookingStatus, EventType
from apps.reviews.models import Review

class ReviewDomainTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Owner
        self.owner = User.objects.create_user(
            email="owner_rev@example.com",
            password="Password123!",
            full_name="M. Reddy",
            role=UserRole.OWNER
        )
        OwnerProfile.objects.create(user=self.owner, business_name="Reddy Conventions", city="Hyderabad")
        self.owner_token = JWTTokenService.generate_tokens_for_user(self.owner)['access_token']

        # Customer 1
        self.customer1 = User.objects.create_user(
            email="cust_rev1@example.com",
            password="Password123!",
            full_name="Kavita Nair",
            role=UserRole.CUSTOMER,
            phone="+919876543333"
        )
        self.cust1_token = JWTTokenService.generate_tokens_for_user(self.customer1)['access_token']

        # Customer 2
        self.customer2 = User.objects.create_user(
            email="cust_rev2@example.com",
            password="Password123!",
            full_name="Rajesh Verma",
            role=UserRole.CUSTOMER,
            phone="+919876544444"
        )
        self.cust2_token = JWTTokenService.generate_tokens_for_user(self.customer2)['access_token']

        # Hall
        self.hall = Hall.objects.create(
            owner=self.owner,
            name="Reddy Grand Palace",
            address_line1="Jubilee Hills",
            city="Hyderabad",
            locality="Jubilee Hills",
            min_capacity=100,
            max_capacity=500,
            base_price_morning=30000,
            base_price_evening=45000,
            base_price_full_day=70000,
            approval_status=HallApprovalStatus.APPROVED,
            status=HallStatus.ACTIVE
        )

        # Completed Booking
        self.completed_booking = Booking.objects.create(
            customer=self.customer1,
            hall=self.hall,
            event_type=EventType.WEDDING,
            event_date=date(2026, 7, 10),
            time_slot=TimeSlot.EVENING,
            guest_count=300,
            contact_name="Kavita Nair",
            contact_phone="+919876543333",
            hall_rent=45000,
            subtotal=45000,
            tax_amount=8100,
            total_amount=53100,
            advance_amount=10620,
            balance_amount=42480,
            amount_paid=53100,
            status=BookingStatus.COMPLETED
        )

    def test_submit_review_on_completed_booking_success_and_aggregates_update(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.cust1_token}")
        payload = {
            "rating": 5,
            "comment": "Outstanding venue, air conditioning was powerful and stage decoration was breathtaking!"
        }
        res = self.client.post(f'/api/v1/bookings/{self.completed_booking.id}/review/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['success'])

        # Hall aggregates should now reflect rating 5.0
        self.hall.refresh_from_db()
        self.assertEqual(self.hall.avg_rating, Decimal('5.00'))
        self.assertEqual(self.hall.review_count, 1)

    def test_review_rejected_if_booking_not_completed(self):
        pending_booking = Booking.objects.create(
            customer=self.customer1,
            hall=self.hall,
            event_type=EventType.BIRTHDAY,
            event_date=date(2026, 9, 20),
            time_slot=TimeSlot.MORNING,
            guest_count=150,
            contact_name="Kavita",
            contact_phone="+919876543333",
            hall_rent=30000,
            subtotal=30000,
            tax_amount=5400,
            total_amount=35400,
            advance_amount=7080,
            balance_amount=28320,
            amount_paid=7080,
            status=BookingStatus.CONFIRMED # Not yet completed!
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.cust1_token}")
        res = self.client.post(f'/api/v1/bookings/{pending_booking.id}/review/', {
            "rating": 4,
            "comment": "Trying to review early"
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(res.data['success'])

    def test_customer_cannot_review_another_customers_booking(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.cust2_token}")
        res = self.client.post(f'/api/v1/bookings/{self.completed_booking.id}/review/', {
            "rating": 5,
            "comment": "Unauthorized review attempt"
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_duplicate_review_on_same_booking_rejected(self):
        # Create initial review
        Review.objects.create(
            booking=self.completed_booking,
            customer=self.customer1,
            hall=self.hall,
            rating=5,
            comment="Initial review"
        )

        # Attempt to submit second review
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.cust1_token}")
        res = self.client.post(f'/api/v1/bookings/{self.completed_booking.id}/review/', {
            "rating": 4,
            "comment": "Second review attempt"
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_respond_to_review(self):
        review = Review.objects.create(
            booking=self.completed_booking,
            customer=self.customer1,
            hall=self.hall,
            rating=5,
            comment="Loved the hospitality!"
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_token}")
        res = self.client.post(f'/api/v1/reviews/{review.id}/respond/', {
            "owner_response": "Thank you Kavita! It was a pleasure hosting your family."
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        review.refresh_from_db()
        self.assertEqual(review.owner_response, "Thank you Kavita! It was a pleasure hosting your family.")
