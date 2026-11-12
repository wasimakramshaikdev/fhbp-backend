from datetime import date, timedelta
from django.test import TestCase
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, UserRole, OwnerProfile
from apps.accounts.authentication import JWTTokenService
from apps.halls.models import Hall, HallApprovalStatus, HallStatus
from apps.availability.models import TimeSlot
from apps.bookings.models import Booking, BookingStatus, EventType

class DashboardDomainTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        self.owner = User.objects.create_user(
            email="owner_dash@example.com",
            password="Password123!",
            full_name="K. Naidu",
            role=UserRole.OWNER
        )
        OwnerProfile.objects.create(user=self.owner, business_name="Grand Orchid LLC", city="Hyderabad")
        self.owner_token = JWTTokenService.generate_tokens_for_user(self.owner)['access_token']

        self.customer = User.objects.create_user(
            email="cust_dash@example.com",
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
            avg_rating=4.5,
            review_count=12,
            approval_status=HallApprovalStatus.APPROVED,
            status=HallStatus.ACTIVE
        )

        # 1. Create Pending Request
        Booking.objects.create(
            customer=self.customer,
            hall=self.hall,
            event_type=EventType.ENGAGEMENT,
            event_date=date(2026, 8, 14),
            time_slot=TimeSlot.MORNING,
            guest_count=200,
            contact_name="A. Reddy",
            contact_phone="+919876543211",
            hall_rent=30000,
            subtotal=30000,
            tax_amount=5400,
            total_amount=35400,
            advance_amount=7080,
            balance_amount=28320,
            amount_paid=7080,
            status=BookingStatus.PENDING_OWNER_CONFIRMATION
        )

        # 2. Create Confirmed Booking
        Booking.objects.create(
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
            amount_paid=53100,
            status=BookingStatus.CONFIRMED
        )

    def test_owner_dashboard_overview_metrics(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_token}")
        res = self.client.get('/api/v1/owner/dashboard/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['success'])

        metrics = res.data['data']['metrics']
        self.assertEqual(metrics['pending_requests'], 1)
        self.assertEqual(metrics['confirmed_this_month'], 1)
        self.assertEqual(metrics['revenue_this_month'], 53100.0)
        self.assertEqual(metrics['avg_rating'], 4.5)

        upcoming = res.data['data']['upcoming_events']
        self.assertEqual(len(upcoming), 2)

    def test_admin_dashboard_includes_refund_metrics(self):
        admin = User.objects.create_user(
            email="admin_dash@example.com",
            password="Password123!",
            full_name="System Admin",
            role=UserRole.ADMIN,
        )
        admin_token = JWTTokenService.generate_tokens_for_user(admin)['access_token']

        refunded_booking = Booking.objects.create(
            customer=self.customer,
            hall=self.hall,
            event_type=EventType.WEDDING,
            event_date=date(2026, 8, 10),
            time_slot=TimeSlot.EVENING,
            guest_count=300,
            contact_name="A. Reddy",
            contact_phone="+919876543211",
            hall_rent=45000,
            subtotal=45000,
            tax_amount=8100,
            total_amount=53100,
            advance_amount=10620,
            balance_amount=42480,
            amount_paid=53100,
            status=BookingStatus.REFUNDED,
            refund_amount=26550,
            created_at=timezone.now() - timedelta(days=2),
        )
        refunded_booking.save(update_fields=['created_at', 'updated_at'])

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_token}")
        res = self.client.get('/api/v1/admin/dashboard/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['success'])
        metrics = res.data['data']['metrics']
        self.assertEqual(metrics['refunds_this_month'], 1)
        self.assertEqual(metrics['refund_amount_mtd'], 26550.0)
        self.assertEqual(metrics['total_refunded_bookings'], 1)
        self.assertEqual(metrics['refunds_due_count'], 0)
        self.assertEqual(len(res.data['data']['refunded_bookings']), 1)
        self.assertEqual(res.data['data']['refunded_bookings'][0]['status'], 'REFUNDED')

    def test_admin_dashboard_tracks_refund_due_bookings(self):
        admin = User.objects.create_user(
            email="admin_refund_due@example.com",
            password="Password123!",
            full_name="Refund Admin",
            role=UserRole.ADMIN,
        )
        admin_token = JWTTokenService.generate_tokens_for_user(admin)['access_token']

        cancelled_booking = Booking.objects.create(
            customer=self.customer,
            hall=self.hall,
            event_type=EventType.WEDDING,
            event_date=date(2026, 8, 9),
            time_slot=TimeSlot.EVENING,
            guest_count=250,
            contact_name="A. Reddy",
            contact_phone="+919876543211",
            hall_rent=45000,
            subtotal=45000,
            tax_amount=8100,
            total_amount=53100,
            advance_amount=10620,
            balance_amount=42480,
            amount_paid=53100,
            status=BookingStatus.CANCELLED_BY_CUSTOMER,
            refund_amount=26550,
            created_at=timezone.now() - timedelta(days=1),
        )
        cancelled_booking.save(update_fields=['created_at', 'updated_at'])

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_token}")
        res = self.client.get('/api/v1/admin/dashboard/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['data']['metrics']['refunds_due_count'], 1)
        self.assertEqual(res.data['data']['metrics']['refunds_due_amount'], 26550.0)

    def test_admin_owner_list_exposes_kyc_documents(self):
        admin = User.objects.create_user(
            email="admin_kyc@example.com",
            password="Password123!",
            full_name="KYC Admin",
            role=UserRole.ADMIN,
        )
        admin_token = JWTTokenService.generate_tokens_for_user(admin)['access_token']

        profile = self.owner.owner_profile
        profile.id_proof = SimpleUploadedFile("id_proof.pdf", b"pdf-bytes", content_type="application/pdf")
        profile.business_proof = SimpleUploadedFile("business_proof.pdf", b"pdf-bytes", content_type="application/pdf")
        profile.verification_status = 'PENDING'
        profile.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_token}")
        res = self.client.get('/api/v1/admin/owners/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['success'])
        owner_data = res.data['data'][0]
        self.assertIn('id_proof_url', owner_data)
        self.assertIn('business_proof_url', owner_data)
        self.assertTrue(owner_data['id_proof_url'].endswith('id_proof.pdf'))
        self.assertTrue(owner_data['business_proof_url'].endswith('business_proof.pdf'))
