from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, UserRole, OwnerProfile, OwnerVerificationStatus
from apps.accounts.authentication import JWTTokenService
from apps.halls.models import Hall, HallApprovalStatus, HallStatus
from apps.availability.models import TimeSlot
from apps.bookings.models import Booking, BookingStatus, EventType
from apps.payments.models import Payment, PaymentStatus
from apps.disputes.models import Dispute, DisputeStatus, DisputeResolutionType

class DisputeAndAdminTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Super Admin
        self.admin = User.objects.create_superuser(
            email="superadmin@hallbook.in",
            password="AdminPassword123!",
            full_name="Platform Admin"
        )
        self.admin_token = JWTTokenService.generate_tokens_for_user(self.admin)['access_token']

        # Owner
        self.owner = User.objects.create_user(
            email="owner_disp@example.com",
            password="Password123!",
            full_name="K. Naidu",
            role=UserRole.OWNER
        )
        OwnerProfile.objects.create(user=self.owner, business_name="Naidu Banquets", city="Hyderabad")

        # Customer
        self.customer = User.objects.create_user(
            email="cust_disp@example.com",
            password="Password123!",
            full_name="A. Reddy",
            role=UserRole.CUSTOMER,
            phone="+919876545555"
        )
        self.customer_token = JWTTokenService.generate_tokens_for_user(self.customer)['access_token']

        # Hall
        self.hall = Hall.objects.create(
            owner=self.owner,
            name="Royal Palms Convention",
            address_line1="Gachibowli",
            city="Hyderabad",
            locality="Gachibowli",
            approval_status=HallApprovalStatus.APPROVED,
            status=HallStatus.ACTIVE
        )

        # Booking
        self.booking = Booking.objects.create(
            customer=self.customer,
            hall=self.hall,
            event_type=EventType.WEDDING,
            event_date=date(2026, 8, 2),
            time_slot=TimeSlot.EVENING,
            guest_count=300,
            contact_name="A. Reddy",
            contact_phone="+919876545555",
            hall_rent=30000,
            subtotal=30000,
            tax_amount=5400,
            total_amount=35400,
            advance_amount=7080,
            balance_amount=28320,
            amount_paid=35400,
            status=BookingStatus.CONFIRMED
        )
        Payment.objects.create(
            booking=self.booking,
            idempotency_key="pay_disp_1",
            amount=35400,
            status=PaymentStatus.SUCCESS,
            gateway="SIMULATED",
            gateway_order_id="ord_disp_1",
            gateway_payment_id="pay_disp_1"
        )

    def test_customer_create_dispute_and_admin_resolve_with_refund(self):
        # 1. Customer creates dispute (Wireframe Screen 7)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.customer_token}")
        disp_payload = {
            "booking_id": str(self.booking.id),
            "reason": "Hall denied entry on event date",
            "description": "Customer claims hall denied entry on date. Owner claims no-show.",
            "evidence_urls": ["https://example.com/gate_receipt.jpg"]
        }
        res_create = self.client.post('/api/v1/disputes/', disp_payload, format='json')
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res_create.data['success'])

        dispute_id = res_create.data['data']['id']
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatus.DISPUTED)

        # 2. Super Admin views dispute list
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        res_list = self.client.get('/api/v1/admin/disputes/')
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_list.data['data']), 1)

        # 3. Super Admin resolves dispute with CUSTOMER_REFUND
        resolve_payload = {
            "resolution_type": "CUSTOMER_REFUND",
            "admin_notes": "Customer presented CCTV entry timestamp proving venue locked. Full refund issued."
        }
        res_resolve = self.client.post(f'/api/v1/admin/disputes/{dispute_id}/resolve/', resolve_payload, format='json')
        self.assertEqual(res_resolve.status_code, status.HTTP_200_OK)

        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatus.REFUNDED)
        self.assertEqual(self.booking.refund_amount, Decimal('35400.00'))

    def test_admin_settings_update_and_audit_trail(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        patch_res = self.client.patch('/api/v1/admin/settings/', {
            "PLATFORM_COMMISSION_PCT": {"percentage": 12.5}
        }, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)

        # Verify audit log recorded
        audit_res = self.client.get('/api/v1/admin/audit-logs/')
        self.assertEqual(audit_res.status_code, status.HTTP_200_OK)
        actions = [log['action'] for log in audit_res.data['data']]
        self.assertIn("ADMIN_UPDATED_PLATFORM_SETTING", actions)
