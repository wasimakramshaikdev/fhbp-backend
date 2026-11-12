import json
import base64
import urllib.parse
import jwt
from decimal import Decimal
from datetime import date, datetime, timezone
from django.test import TestCase
from django.conf import settings
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, UserRole, OwnerProfile
from apps.accounts.authentication import JWTTokenService
from apps.halls.models import Hall, HallApprovalStatus, HallStatus
from apps.availability.models import TimeSlot
from apps.bookings.models import Booking, BookingStatus, EventType
from apps.payments.models import Payment, PaymentStatus
from apps.disputes.models import Dispute, DisputeStatus

class SecurityHardeningTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Admin
        self.admin = User.objects.create_superuser(
            email="security_admin@hallbook.in",
            password="AdminPassword123!",
            full_name="Platform Admin"
        )
        self.admin_token = JWTTokenService.generate_tokens_for_user(self.admin)['access_token']

        # Owner A
        self.owner_a = User.objects.create_user(
            email="owner_a_sec@example.com",
            password="Password123!",
            full_name="Owner Alpha",
            role=UserRole.OWNER
        )
        OwnerProfile.objects.create(
            user=self.owner_a,
            business_name="Alpha Banquets",
            bank_account_holder="Alpha LLC",
            bank_account_number="1111222233334444",
            bank_ifsc_code="HDFC0001111",
            city="Hyderabad"
        )
        self.owner_a_token = JWTTokenService.generate_tokens_for_user(self.owner_a)['access_token']

        # Owner B
        self.owner_b = User.objects.create_user(
            email="owner_b_sec@example.com",
            password="Password123!",
            full_name="Owner Beta",
            role=UserRole.OWNER
        )
        OwnerProfile.objects.create(
            user=self.owner_b,
            business_name="Beta Banquets",
            bank_account_holder="Beta LLC",
            bank_account_number="5555666677778888",
            bank_ifsc_code="ICIC0002222",
            city="Hyderabad"
        )
        self.owner_b_token = JWTTokenService.generate_tokens_for_user(self.owner_b)['access_token']

        # Customer A
        self.cust_a = User.objects.create_user(
            email="cust_a_sec@example.com",
            password="Password123!",
            full_name="Customer Alice",
            role=UserRole.CUSTOMER,
            phone="+919876500001"
        )
        self.cust_a_token = JWTTokenService.generate_tokens_for_user(self.cust_a)['access_token']

        # Customer B
        self.cust_b = User.objects.create_user(
            email="cust_b_sec@example.com",
            password="Password123!",
            full_name="Customer Bob",
            role=UserRole.CUSTOMER,
            phone="+919876500002"
        )
        self.cust_b_token = JWTTokenService.generate_tokens_for_user(self.cust_b)['access_token']

        # Hall A (Owned by Owner A)
        self.hall_a = Hall.objects.create(
            owner=self.owner_a,
            name="Alpha Grand Banquet",
            address_line1="Road 36, Madhapur",
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

        # Booking A (Customer Alice at Hall A)
        self.booking_a = Booking.objects.create(
            customer=self.cust_a,
            hall=self.hall_a,
            event_type=EventType.WEDDING,
            event_date=date(2026, 8, 25),
            time_slot=TimeSlot.EVENING,
            guest_count=300,
            contact_name="Alice",
            contact_phone="+919876500001",
            hall_rent=45000,
            subtotal=45000,
            tax_amount=8100,
            total_amount=53100,
            advance_amount=10620,
            balance_amount=42480,
            amount_paid=10620,
            status=BookingStatus.PENDING_OWNER_CONFIRMATION
        )

    def test_idor_customer_cannot_access_other_customer_booking(self):
        """Customer B must NEVER be able to read Customer A's booking."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.cust_b_token}")
        res = self.client.get(f'/api/v1/bookings/{self.booking_a.id}/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_idor_customer_cannot_pay_for_other_customer_booking(self):
        """Customer B cannot initiate a payment for Customer A's booking."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.cust_b_token}")
        res = self.client.post('/api/v1/payments/initiate/', {
            "booking_id": str(self.booking_a.id),
            "payment_type": "BALANCE"
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_idor_owner_cannot_modify_another_owners_hall(self):
        """Owner B cannot patch, delete, or upload images to Owner A's venue."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_b_token}")
        res = self.client.patch(f'/api/v1/owner/listings/{self.hall_a.id}/', {
            "name": "Hacked Alpha Venue"
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.hall_a.refresh_from_db()
        self.assertEqual(self.hall_a.name, "Alpha Grand Banquet")

    def test_role_escalation_customer_cannot_access_admin_dashboard(self):
        """Regular customer cannot query admin endpoints."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.cust_a_token}")
        res = self.client.get('/api/v1/admin/dashboard/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_role_escalation_owner_cannot_access_admin_settings(self):
        """Venue owner cannot query or patch platform commission settings."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_a_token}")
        res = self.client.patch('/api/v1/admin/settings/', {
            "PLATFORM_COMMISSION_PCT": {"percentage": 0.0}
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_forged_jwt_signature_rejected(self):
        """Forged JWT signed with incorrect secret key is rejected immediately."""
        tampered_token = jwt.encode(
            {"user_id": str(self.admin.id), "email": "superadmin@hallbook.in", "role": "ADMIN", "type": "access"},
            "wrong-forged-secret-key-12345-67890-abcdef",
            algorithm="HS256"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tampered_token}")
        res = self.client.get('/api/v1/auth/me/')
        self.assertIn(res.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_bank_account_masking_in_api_responses(self):
        """Owner bank account number must be masked in JSON outputs (e.g. **** **** 4444)."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_a_token}")
        res = self.client.get('/api/v1/auth/me/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        owner_data = res.data['data']['owner_profile']
        self.assertEqual(owner_data['masked_bank_account'], '**** **** 4444')
        self.assertNotIn('1111222233334444', str(res.data))

    def test_webhook_invalid_signature_rejected(self):
        """Payment webhook callback with invalid signature is rejected."""
        webhook_payload = {
            "order_id": "order_test_12345",
            "payment_id": "pay_test_12345",
            "signature": "forged_malicious_signature_hash"
        }
        res = self.client.post('/api/v1/payments/webhook/', webhook_payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_malicious_svg_or_executable_image_urls_rejected(self):
        """Malicious SVG / executable extensions in hall image uploads must be rejected."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_a_token}")
        
        # Test malicious SVG
        res_svg = self.client.post(f'/api/v1/owner/listings/{self.hall_a.id}/images/', {
            "images": ["https://example.com/exploit.svg"]
        }, format='json')
        self.assertEqual(res_svg.status_code, status.HTTP_400_BAD_REQUEST)

        # Test executable / script
        res_php = self.client.post(f'/api/v1/owner/listings/{self.hall_a.id}/images/', {
            "images": ["https://example.com/shell.php"]
        }, format='json')
        self.assertEqual(res_php.status_code, status.HTTP_400_BAD_REQUEST)

    def test_arena_auth_cookie_authentication_supported(self):
        """Django JWTAuthentication must extract access_token from arena-auth-prod-v1.0 cookie."""
        tokens = JWTTokenService.generate_tokens_for_user(self.cust_a)
        raw_auth_obj = {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "expires_in": 3600,
            "user": {"id": str(self.cust_a.id), "email": self.cust_a.email}
        }
        url_encoded_cookie = urllib.parse.quote(json.dumps(raw_auth_obj))

        # Make request with NO Authorization header, only cookie
        self.client.credentials()  # No Authorization header
        self.client.cookies["arena-auth-prod-v1.0"] = url_encoded_cookie

        res = self.client.get('/api/v1/auth/me/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['data']['email'], "cust_a_sec@example.com")

    def test_arena_auth_base64_json_cookie_supported(self):
        """Django JWTAuthentication must correctly parse Base64-encoded JSON in arena-auth-prod-v1.1 cookie."""
        tokens = JWTTokenService.generate_tokens_for_user(self.cust_b)
        raw_auth_obj = {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "expires_in": 3600,
            "user": {"id": str(self.cust_b.id), "email": self.cust_b.email}
        }
        b64_cookie = base64.b64encode(json.dumps(raw_auth_obj).encode()).decode()

        self.client.credentials()
        self.client.cookies["arena-auth-prod-v1.1"] = b64_cookie

        res = self.client.get('/api/v1/auth/me/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['data']['email'], "cust_b_sec@example.com")

    def test_header_precedence_over_cookie(self):
        """Authorization header token takes precedence over cookie token."""
        tokens_a = JWTTokenService.generate_tokens_for_user(self.cust_a)
        tokens_b = JWTTokenService.generate_tokens_for_user(self.cust_b)

        # Cookie is for user A, Header is for user B
        self.client.cookies["arena-auth-prod-v1.0"] = tokens_a["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens_b['access_token']}")

        res = self.client.get('/api/v1/auth/me/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Must authenticate as User B from Header
        self.assertEqual(res.data['data']['email'], "cust_b_sec@example.com")

    def test_unauthenticated_request_returns_401_with_www_authenticate(self):
        """Unauthenticated request to protected endpoint returns HTTP 401 with WWW-Authenticate."""
        self.client.credentials()
        self.client.cookies.clear()

        res = self.client.get('/api/v1/auth/me/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('WWW-Authenticate', res.headers)
