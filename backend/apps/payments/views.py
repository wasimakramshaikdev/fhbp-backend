import json
import logging
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from apps.core.responses import api_response
from apps.core.pagination import StandardPagination
from apps.bookings.models import Booking
from apps.payments.models import Payment, PaymentStatus
from apps.payments.services.payment import PaymentService, PaymentProcessingError
from apps.payments.services.gateway import (
    get_payment_gateway,
    PaymentGatewayError,
    PaymentGatewayConfigurationError,
)
from apps.payments.services.invoice import InvoiceService
from apps.payments.serializers import (
    PaymentInitiateSerializer,
    PaymentVerifySerializer,
    PaymentListSerializer,
)

logger = logging.getLogger(__name__)

class PaymentInitiateView(APIView):
    """
    Creates a payment order on Razorpay / payment gateway for advance or balance settlement.
    Accessible via /api/v1/payments/initiate/ and /api/v1/payments/razorpay/order/.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PaymentInitiateSerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(
                message="Invalid payment parameters.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="VALIDATION_ERROR"
            )

        booking_id = serializer.validated_data['booking_id']
        payment_type = serializer.validated_data.get('payment_type', 'ADVANCE')
        payment_method = serializer.validated_data.get('payment_method', 'UPI')

        booking = Booking.objects.filter(id=booking_id).first()
        if not booking:
            return api_response(
                message="Booking not found.",
                status_code=status.HTTP_404_NOT_FOUND,
                success=False,
                code="BOOKING_NOT_FOUND"
            )

        # IDOR Authorization Guard: Only the customer who owns the booking (or Super Admin) can initiate payment
        if booking.customer != request.user and not request.user.is_admin:
            return api_response(
                message="You are not authorized to make payments for this booking.",
                status_code=status.HTTP_403_FORBIDDEN,
                success=False,
                code="FORBIDDEN"
            )

        try:
            order_data = PaymentService.initiate_payment(
                booking=booking,
                payment_type=payment_type,
                payment_method=payment_method,
                actor=request.user
            )
            return api_response(
                data=order_data,
                message="Payment order initiated successfully.",
                status_code=status.HTTP_201_CREATED
            )
        except PaymentGatewayConfigurationError as exc:
            return api_response(
                message="Razorpay payment configuration is not available.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                success=False,
                code="RAZORPAY_NOT_CONFIGURED"
            )
        except (PaymentProcessingError, PaymentGatewayError) as exc:
            return api_response(
                message=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="PAYMENT_INITIATION_FAILED"
            )


class PaymentVerifyView(APIView):
    """
    Cryptographically verifies gateway signature and atomically confirms payment.
    Accessible via /api/v1/payments/verify/ and /api/v1/payments/razorpay/verify/.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PaymentVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(
                message="Verification payload invalid.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="VALIDATION_ERROR"
            )

        order_id = serializer.validated_data['gateway_order_id']
        payment_id = serializer.validated_data['gateway_payment_id']
        signature = serializer.validated_data['gateway_signature']

        try:
            payment = PaymentService.verify_and_confirm_payment(
                gateway_order_id=order_id,
                gateway_payment_id=payment_id,
                gateway_signature=signature,
                actor=request.user
            )
            return api_response(
                data=PaymentListSerializer(payment).data,
                message="Payment confirmed successfully!"
            )
        except PaymentGatewayConfigurationError as exc:
            return api_response(
                message="Razorpay payment configuration is not available.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                success=False,
                code="RAZORPAY_NOT_CONFIGURED"
            )
        except (PaymentProcessingError, PaymentGatewayError) as exc:
            return api_response(
                message=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="VERIFICATION_FAILED"
            )


class PaymentWebhookView(APIView):
    """
    Public webhook receiver with cryptographic HMAC validation and idempotency.
    Extracts Razorpay signature from HTTP header 'X-Razorpay-Signature'.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        # 1. Extract signature from HTTP Header (Primary) or body
        signature = (
            request.headers.get('X-Razorpay-Signature')
            or request.META.get('HTTP_X_RAZORPAY_SIGNATURE')
            or request.data.get('signature')
        )

        if not signature:
            return api_response(
                message="Webhook signature header missing.",
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="MISSING_SIGNATURE"
            )

        payload = request.data

        # 2. Extract order_id and payment_id from Razorpay webhook structure or flat JSON
        payment_entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
        order_id = payment_entity.get('order_id') or payload.get('order_id')
        payment_id = payment_entity.get('id') or payload.get('payment_id')

        if not (order_id and payment_id):
            return api_response(
                message="Webhook payload missing order_id or payment_id.",
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="INVALID_PAYLOAD"
            )

        # 3. Verify signature cryptographically
        gateway = get_payment_gateway()
        try:
            is_valid = gateway.verify_webhook_signature(
                raw_body=request.body,
                signature=signature,
                order_id=order_id,
                payment_id=payment_id
            )
        except Exception as e:
            is_valid = False

        if not is_valid:
            return api_response(
                message="Invalid cryptographic signature on webhook.",
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="INVALID_SIGNATURE"
            )

        try:
            payment = PaymentService.verify_and_confirm_payment(
                gateway_order_id=order_id,
                gateway_payment_id=payment_id,
                gateway_signature=signature
            )
            return api_response(
                data={"payment_reference": payment.payment_reference, "status": payment.status},
                message="Webhook processed successfully."
            )
        except Exception as exc:
            logger.error(f"Webhook processing error: {exc}", exc_info=True)
            return api_response(message=str(exc), status_code=status.HTTP_400_BAD_REQUEST, success=False)


class BookingInvoiceView(APIView):
    """
    Retrieves full GST compliant tax invoice breakdown for a booking.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, booking_id):
        booking = Booking.objects.filter(id=booking_id).select_related('hall', 'customer', 'hall__owner', 'hall__owner__owner_profile').prefetch_related('payments').first()
        if not booking:
            return api_response(message="Booking not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

        # IDOR Authorization
        if booking.customer != request.user and booking.hall.owner != request.user and not request.user.is_admin:
            return api_response(message="Permission denied.", status_code=status.HTTP_403_FORBIDDEN, success=False)

        invoice_data = InvoiceService.generate_invoice_data(booking)
        return api_response(data=invoice_data)


class CustomerInvoiceListView(APIView):
    """
    Lists all invoices/payments for the authenticated customer.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payments = Payment.objects.filter(booking__customer=request.user, status=PaymentStatus.SUCCESS).select_related('booking', 'booking__hall').order_by('-paid_at')
        paginator = StandardPagination()
        page = paginator.paginate_queryset(payments, request)
        serializer = PaymentListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
