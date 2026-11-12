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
from apps.payouts.models import Payout, PayoutStatus
from apps.payouts.services.payout import PayoutService

class PayoutDomainTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        self.owner = User.objects.create_user(
            email="owner_payout@example.com",
            password="Password123!",
            full_name="K. Naidu",
            role=UserRole.OWNER
        )
        OwnerProfile.objects.create(
            user=self.owner,
            business_name="Grand Orchid Conventions",
            pan_gst_number="36AABCG1234F1Z5",
            bank_account_holder="Grand Orchid LLC",
            bank_account_number="12345678901234",
            bank_ifsc_code="HDFC0001234",
            city="Hyderabad"
        )
        self.owner_token = JWTTokenService.generate_tokens_for_user(self.owner)['access_token']

        self.customer = User.objects.create_user(
            email="cust_payout@example.com",
            password="Password123!",
            full_name="R. Sharma",
            role=UserRole.CUSTOMER
        )

        self.hall = Hall.objects.create(
            owner=self.owner,
            name="Grand Orchid Banquets",
            address_line1="Road 36, Madhapur",
            city="Hyderabad",
            locality="Madhapur",
            min_capacity=100,
            max_capacity=500,
            base_price_morning=30000,
            base_price_evening=45000,
            base_price_full_day=70000,
            advance_percentage=20,
            approval_status=HallApprovalStatus.APPROVED,
            status=HallStatus.ACTIVE
        )

        # Confirmed Booking with ₹45,000 paid
        self.booking = Booking.objects.create(
            customer=self.customer,
            hall=self.hall,
            event_type=EventType.WEDDING,
            event_date=date(2026, 8, 12),
            time_slot=TimeSlot.EVENING,
            guest_count=350,
            contact_name="R. Sharma",
            contact_phone="+919876543210",
            hall_rent=45000,
            subtotal=45000,
            tax_amount=8100,
            total_amount=53100,
            advance_amount=10620,
            balance_amount=42480,
            amount_paid=45000,
            status=BookingStatus.CONFIRMED
        )

    def test_commission_calculation_and_payout_scheduling(self):
        payout = PayoutService.schedule_payout_for_booking(self.booking)
        # Gross: 45,000
        # Commission (10%): 4,500
        # Net: 40,500
        self.assertEqual(payout.gross_amount, Decimal('45000.00'))
        self.assertEqual(payout.commission_amount, Decimal('4500.00'))
        self.assertEqual(payout.net_amount, Decimal('40500.00'))
        self.assertEqual(payout.payout_date, date(2026, 8, 15)) # Event date + 3 days
        self.assertEqual(payout.status, PayoutStatus.SCHEDULED)

    def test_owner_earnings_endpoint_retrieval(self):
        PayoutService.schedule_payout_for_booking(self.booking)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_token}")
        res = self.client.get('/api/v1/owner/earnings/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['success'])

        summary = res.data['data']['summary']
        self.assertEqual(summary['total_gross'], 45000.0)
        self.assertEqual(summary['total_commission'], 4500.0)
        self.assertEqual(summary['total_net'], 40500.0)
        self.assertEqual(summary['commission_rate_pct'], 10.0)
        self.assertEqual(len(res.data['data']['payouts']), 1)
