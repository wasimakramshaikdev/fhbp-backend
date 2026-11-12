from decimal import Decimal
from datetime import date
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, UserRole, OwnerProfile
from apps.accounts.authentication import JWTTokenService
from apps.halls.models import Hall, HallApprovalStatus, HallStatus
from apps.availability.models import TimeSlot
from apps.bookings.models import Booking, BookingStatus, EventType
from apps.bookings.services.booking import BookingService
from apps.payments.models import Payment, PaymentStatus, PaymentType, PaymentMethod
from apps.payments.services.payment import PaymentService, PaymentProcessingError
from apps.payments.services.invoice import InvoiceService
from apps.payments.services.gateway import (
    RazorpayGatewayAdapter,
    SimulatedGatewayAdapter,
    PaymentGatewayConfigurationError,
    PaymentGatewayError,
)

class PaymentDomainTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Owner
        self.owner = User.objects.create_user(
            email="owner_pay@example.com",
            password="Password123!",
            full_name="K. Naidu",
            role=UserRole.OWNER
        )
        OwnerProfile.objects.create(
            user=self.owner,
            business_name="Grand Orchid Banquets LLC",
            pan_gst_number="36AABCG1234F1Z5",
            city="Hyderabad"
        )
        self.owner_token = JWTTokenService.generate_tokens_for_user(self.owner)['access_token']

        # Customer A
        self.customer = User.objects.create_user(
            email="cust_pay@example.com",
            password="Password123!",
            full_name="Anil Kumar",
            role=UserRole.CUSTOMER,
            phone="+919876541111"
        )
        self.customer_token = JWTTokenService.generate_tokens_for_user(self.customer)['access_token']

        # Customer B (for IDOR tests)
        self.customer_b = User.objects.create_user(
            email="cust_b_pay@example.com",
            password="Password123!",
            full_name="Other User",
            role=UserRole.CUSTOMER,
            phone="+919876542222"
        )
        self.customer_b_token = JWTTokenService.generate_tokens_for_user(self.customer_b)['access_token']

        # Hall
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
            veg_plate_price=500,
            approval_status=HallApprovalStatus.APPROVED,
            status=HallStatus.ACTIVE
        )

        # Create Booking (Rent: 45,000 + Catering: 100,000 = 145,000. Tax: 26,100. Total: 171,100. Advance: 34,220.)
        self.booking = BookingService.create_booking_intent(
            customer=self.customer,
            hall=self.hall,
            event_type=EventType.WEDDING,
            event_date=date(2026, 9, 10),
            time_slot=TimeSlot.EVENING,
            guest_count=200,
            contact_name="Anil Kumar",
            contact_phone="+919876541111",
            has_catering=True,
            catering_type="VEG"
        )

    def test_unauthenticated_payment_initiate_returns_401(self):
        """Unauthenticated request to payment initiate returns 401 with WWW-Authenticate."""
        self.client.credentials()  # No token
        res = self.client.post('/api/v1/payments/initiate/', {
            "booking_id": str(self.booking.id),
            "payment_type": "ADVANCE"
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_idor_customer_cannot_pay_for_another_customers_booking(self):
        """Customer B cannot initiate a payment order for Customer A's booking."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.customer_b_token}")
        res = self.client.post('/api/v1/payments/razorpay/order/', {
            "booking_id": str(self.booking.id),
            "payment_type": "ADVANCE"
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(res.data['success'])

    @override_settings(PAYMENT_GATEWAY_PROVIDER='SIMULATED')
    def test_initiate_payment_order_success(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.customer_token}")
        payload = {
            "booking_id": str(self.booking.id),
            "payment_type": "ADVANCE",
            "payment_method": "UPI"
        }
        res = self.client.post('/api/v1/payments/initiate/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['success'])
        self.assertEqual(Decimal(str(res.data['data']['amount'])), Decimal('34220.00'))
        self.assertIn('gateway_order_id', res.data['data'])
        self.assertIn('amount_subunits', res.data['data'])
        self.assertEqual(res.data['data']['amount_subunits'], 3422000)

    @override_settings(PAYMENT_GATEWAY_PROVIDER='SIMULATED')
    def test_verify_payment_success_and_state_transition(self):
        init_res = PaymentService.initiate_payment(self.booking, payment_type=PaymentType.ADVANCE)
        order_id = init_res['gateway_order_id']

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.customer_token}")
        verify_payload = {
            "gateway_order_id": order_id,
            "gateway_payment_id": "pay_test_123456",
            "gateway_signature": "valid_simulated_signature"
        }
        res = self.client.post('/api/v1/payments/verify/', verify_payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['success'])

        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatus.PENDING_OWNER_CONFIRMATION)
        self.assertEqual(self.booking.amount_paid, Decimal('34220.00'))

    @override_settings(PAYMENT_GATEWAY_PROVIDER='SIMULATED')
    def test_payment_idempotency_does_not_duplicate_credits(self):
        init_res = PaymentService.initiate_payment(self.booking, payment_type=PaymentType.ADVANCE)
        order_id = init_res['gateway_order_id']

        # Call verify twice
        PaymentService.verify_and_confirm_payment(order_id, "pay_1", "valid_simulated_signature")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.amount_paid, Decimal('34220.00'))

        # Second call
        PaymentService.verify_and_confirm_payment(order_id, "pay_1", "valid_simulated_signature")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.amount_paid, Decimal('34220.00'))  # Unchanged!

    @override_settings(PAYMENT_GATEWAY_PROVIDER='SIMULATED')
    def test_invalid_signature_rejected(self):
        init_res = PaymentService.initiate_payment(self.booking, payment_type=PaymentType.ADVANCE)
        order_id = init_res['gateway_order_id']

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.customer_token}")
        verify_payload = {
            "gateway_order_id": order_id,
            "gateway_payment_id": "pay_test_tampered",
            "gateway_signature": "invalid_forged_signature_hex"
        }
        res = self.client.post('/api/v1/payments/razorpay/verify/', verify_payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(res.data['success'])
        self.assertEqual(res.data['code'], "VERIFICATION_FAILED")

        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatus.PAYMENT_PENDING)
        self.assertEqual(self.booking.amount_paid, Decimal('0.00'))

    @override_settings(PAYMENT_GATEWAY_PROVIDER='RAZORPAY', RAZORPAY_KEY_ID='', RAZORPAY_KEY_SECRET='')
    def test_missing_razorpay_credentials_returns_safe_error(self):
        """When Razorpay keys are not configured, initiate returns safe 503 error without crashing."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.customer_token}")
        res = self.client.post('/api/v1/payments/razorpay/order/', {
            "booking_id": str(self.booking.id),
            "payment_type": "ADVANCE"
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertFalse(res.data['success'])
        self.assertEqual(res.data['message'], "Razorpay payment configuration is not available.")
        self.assertNotIn("secret", str(res.data).lower())

    @override_settings(
        PAYMENT_GATEWAY_PROVIDER='RAZORPAY',
        RAZORPAY_KEY_ID='rzp_test_sample_key_id_123',
        RAZORPAY_KEY_SECRET='rzp_test_sample_secret_key_456'
    )
    @patch('razorpay.Client')
    def test_razorpay_order_creation_mocked(self, mock_client_class):
        """Tests Razorpay SDK integration for creating orders with correct paise amount and receipt."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.order.create.return_value = {
            "id": "order_rzp_mock_123456",
            "amount": 3422000,
            "currency": "INR",
            "status": "created",
            "receipt": self.booking.booking_number
        }

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.customer_token}")
        res = self.client.post('/api/v1/payments/razorpay/order/', {
            "booking_id": str(self.booking.id),
            "payment_type": "ADVANCE"
        }, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['success'])
        self.assertEqual(res.data['data']['gateway_order_id'], "order_rzp_mock_123456")
        self.assertEqual(res.data['data']['key_id'], "rzp_test_sample_key_id_123")
        self.assertNotIn("rzp_test_sample_secret_key_456", str(res.data))

        # Verify SDK called with expected arguments
        mock_client.order.create.assert_called_once()
        call_args = mock_client.order.create.call_args[1]['data']
        self.assertEqual(call_args['amount'], 3422000)
        self.assertEqual(call_args['currency'], 'INR')
        self.assertEqual(call_args['receipt'], self.booking.booking_number)

    @override_settings(
        PAYMENT_GATEWAY_PROVIDER='RAZORPAY',
        RAZORPAY_KEY_ID='rzp_test_sample_key_id_123',
        RAZORPAY_KEY_SECRET='rzp_test_sample_secret_key_456'
    )
    @patch('razorpay.Client')
    def test_razorpay_payment_signature_verification_mocked(self, mock_client_class):
        """Tests Razorpay payment verification with signature verification."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.order.create.return_value = {
            "id": "order_rzp_ver_999",
            "amount": 3422000,
            "currency": "INR",
            "status": "created",
            "receipt": self.booking.booking_number
        }

        # 1. Initiate order
        init_res = PaymentService.initiate_payment(self.booking, payment_type=PaymentType.ADVANCE)
        order_id = init_res['gateway_order_id']

        # 2. Verify signature
        mock_client.utility.verify_payment_signature.return_value = True

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.customer_token}")
        verify_res = self.client.post('/api/v1/payments/razorpay/verify/', {
            "gateway_order_id": order_id,
            "gateway_payment_id": "pay_rzp_test_captured_001",
            "gateway_signature": "mock_valid_signature_hex"
        }, format='json')

        self.assertEqual(verify_res.status_code, status.HTTP_200_OK)
        self.assertTrue(verify_res.data['success'])

        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatus.PENDING_OWNER_CONFIRMATION)
        self.assertEqual(self.booking.amount_paid, Decimal('34220.00'))

    @override_settings(PAYMENT_GATEWAY_PROVIDER='SIMULATED')
    def test_webhook_header_signature_verification(self):
        init_res = PaymentService.initiate_payment(self.booking, payment_type=PaymentType.ADVANCE)
        order_id = init_res['gateway_order_id']

        webhook_payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_webhook_live_99",
                        "order_id": order_id,
                        "amount": 3422000,
                        "currency": "INR",
                        "status": "captured"
                    }
                }
            }
        }
        res = self.client.post(
            '/api/v1/payments/webhook/',
            webhook_payload,
            format='json',
            HTTP_X_RAZORPAY_SIGNATURE='valid_webhook_sig'
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['success'])

        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatus.PENDING_OWNER_CONFIRMATION)
        self.assertEqual(self.booking.amount_paid, Decimal('34220.00'))

    def test_invoice_generation_structure(self):
        with override_settings(PAYMENT_GATEWAY_PROVIDER='SIMULATED'):
            init_res = PaymentService.initiate_payment(self.booking, payment_type=PaymentType.ADVANCE)
            PaymentService.verify_and_confirm_payment(init_res['gateway_order_id'], "pay_inv", "valid_simulated_signature")
        self.booking.refresh_from_db()

        invoice = InvoiceService.generate_invoice_data(self.booking)
        self.assertIn("invoice_number", invoice)
        self.assertEqual(invoice["seller"]["gstin"], "36AABCG1234F1Z5")
        self.assertEqual(len(invoice["items"]), 2)  # Hall Rent + Catering
        self.assertEqual(invoice["financial_summary"]["cgst_rate_pct"], 9.0)
        self.assertEqual(invoice["financial_summary"]["sgst_rate_pct"], 9.0)
        self.assertEqual(invoice["financial_summary"]["grand_total"], 171100.0)
        self.assertEqual(invoice["financial_summary"]["amount_paid"], 34220.0)
        self.assertEqual(invoice["financial_summary"]["balance_due"], 136880.0)
