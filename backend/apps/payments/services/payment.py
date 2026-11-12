import logging
from datetime import datetime, timezone
from decimal import Decimal
from django.db import transaction
from apps.core.services.audit import AuditService
from apps.bookings.models import Booking, BookingStatus
from apps.payments.models import Payment, Refund, PaymentType, PaymentStatus, PaymentMethod
from apps.payments.services.gateway import (
    get_payment_gateway,
    PaymentGatewayError,
    PaymentGatewayConfigurationError
)
from apps.notifications.services.notification import NotificationService

logger = logging.getLogger(__name__)

class PaymentProcessingError(Exception):
    pass

class PaymentService:
    @classmethod
    def initiate_payment(
        cls,
        booking: Booking,
        payment_type: str = PaymentType.ADVANCE,
        payment_method: str = PaymentMethod.UPI,
        actor=None
    ) -> dict:
        """
        Creates an order on Razorpay / payment gateway and records an INITIATED payment record.
        """
        now_utc = datetime.now(timezone.utc)

        # Verify hold expiry for new bookings
        if booking.status == BookingStatus.PAYMENT_PENDING and booking.expires_at:
            if booking.expires_at <= now_utc:
                raise PaymentProcessingError("The 15-minute reservation hold has expired. Please select a time slot again.")

        # Determine authoritative amount server-side using Decimal arithmetic
        if payment_type == PaymentType.ADVANCE:
            if booking.status not in [BookingStatus.PAYMENT_PENDING, BookingStatus.PENDING_OWNER_CONFIRMATION]:
                raise PaymentProcessingError(f"Booking is not in a payable advance state (current status: {booking.status}).")
            amount = booking.advance_amount
        elif payment_type == PaymentType.BALANCE:
            if booking.status not in [BookingStatus.CONFIRMED, BookingStatus.PENDING_OWNER_CONFIRMATION]:
                raise PaymentProcessingError(f"Cannot pay balance for booking with status {booking.status}.")
            amount = booking.total_amount - booking.amount_paid
            if amount <= Decimal('0.00'):
                raise PaymentProcessingError("Booking is already fully paid.")
        elif payment_type == PaymentType.FULL:
            amount = booking.total_amount
        else:
            amount = booking.advance_amount

        if amount <= Decimal('0.00'):
            raise PaymentProcessingError("Payment amount must be greater than zero.")

        idempotency_key = f"pay_{booking.id}_{payment_type}_{int(now_utc.timestamp())}"
        gateway = get_payment_gateway()

        order_data = gateway.create_order(
            amount=amount,
            currency="INR",
            receipt=booking.booking_number,
            notes={
                "booking_id": str(booking.id),
                "booking_number": booking.booking_number,
                "payment_type": payment_type,
            }
        )

        with transaction.atomic():
            payment = Payment.objects.create(
                booking=booking,
                idempotency_key=idempotency_key,
                amount=amount,
                currency="INR",
                payment_type=payment_type,
                payment_method=payment_method,
                status=PaymentStatus.INITIATED,
                gateway="RAZORPAY" if "rzp" in order_data.get('key_id', '') or "order_" in order_data.get('gateway_order_id', '') else "SIMULATED",
                gateway_order_id=order_data["gateway_order_id"],
                gateway_response_payload=order_data,
            )

            AuditService.log_action(
                actor=actor or booking.customer,
                action="PAYMENT_INITIATED",
                obj=payment,
                changes={
                    "amount": str(amount),
                    "type": payment_type,
                    "order_id": order_data["gateway_order_id"]
                }
            )

        return {
            "payment_id": str(payment.id),
            "payment_reference": payment.payment_reference,
            "gateway_order_id": order_data["gateway_order_id"],
            "order_id": order_data["gateway_order_id"],
            "amount": float(amount),
            "amount_subunits": order_data.get("amount_subunits", int(amount * 100)),
            "currency": "INR",
            "key_id": order_data["key_id"],
            "booking_id": str(booking.id),
            "booking_number": booking.booking_number,
            "business_name": booking.hall.name,
            "contact_name": booking.contact_name,
            "contact_email": booking.customer.email,
            "contact_phone": booking.contact_phone,
        }

    @classmethod
    def verify_and_confirm_payment(
        cls,
        gateway_order_id: str,
        gateway_payment_id: str,
        gateway_signature: str,
        actor=None
    ) -> Payment:
        """
        Pessimistic concurrency-locked payment confirmation.
        Verifies signature, ensures idempotency, and updates booking state atomically.
        """
        gateway = get_payment_gateway()

        with transaction.atomic():
            # 1. Acquire row-level lock on Payment record
            payment = Payment.objects.select_for_update().filter(gateway_order_id=gateway_order_id).first()
            if not payment:
                raise PaymentProcessingError(f"No payment transaction found for order ID '{gateway_order_id}'.")

            # 2. Idempotency check: if already processed, return immediately without re-applying
            if payment.status == PaymentStatus.SUCCESS:
                logger.info(f"Payment {payment.payment_reference} is already confirmed. Returning idempotently.")
                return payment

            # 3. Cryptographic Signature Verification
            is_valid = gateway.verify_signature(
                order_id=gateway_order_id,
                payment_id=gateway_payment_id,
                signature=gateway_signature
            )

            if not is_valid:
                payment.status = PaymentStatus.FAILED
                payment.error_message = "Invalid cryptographic signature from gateway."
                payment.save()
                raise PaymentProcessingError("Payment verification failed due to invalid signature.")

            # 4. Mark Payment Successful
            now_utc = datetime.now(timezone.utc)
            payment.status = PaymentStatus.SUCCESS
            payment.gateway_payment_id = gateway_payment_id
            payment.gateway_signature = gateway_signature
            payment.paid_at = now_utc
            payment.save()

            # 5. Lock and Update Booking State
            booking = Booking.objects.select_for_update().get(id=payment.booking.id)
            booking.amount_paid += payment.amount

            if payment.payment_type == PaymentType.ADVANCE or booking.status == BookingStatus.PAYMENT_PENDING:
                booking.status = BookingStatus.PENDING_OWNER_CONFIRMATION

            booking.save()

            # 6. Notify Customer & Owner
            try:
                NotificationService.notify_payment_success(payment)
            except Exception as e:
                logger.warning(f"Failed to dispatch notification for payment {payment.id}: {e}")

            AuditService.log_action(
                actor=actor or booking.customer,
                action="PAYMENT_SUCCESS_VERIFIED",
                obj=payment,
                changes={
                    "status": "SUCCESS",
                    "payment_id": gateway_payment_id,
                    "booking_status": booking.status,
                    "amount_paid": str(booking.amount_paid)
                }
            )

            return payment

    @classmethod
    def execute_refund(
        cls,
        payment_id: str,
        amount: Decimal = None,
        reason: str = "Admin approved refund",
        actor=None
    ) -> Refund:
        """
        Executes gateway refund and records audit trail.
        """
        gateway = get_payment_gateway()

        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(id=payment_id)
            refund_amount = amount or payment.amount
            refund_amount = refund_amount.quantize(Decimal('0.01')) if isinstance(refund_amount, Decimal) else Decimal(str(refund_amount)).quantize(Decimal('0.01'))

            if payment.status == PaymentStatus.REFUNDED and payment.refunds.exists():
                existing_refund = payment.refunds.order_by('-created_at').first()
                return existing_refund

            if refund_amount <= Decimal('0.00'):
                raise PaymentProcessingError("Refund amount must be greater than zero.")

            gateway_resp = gateway.process_refund(
                payment_id=payment.gateway_payment_id or "sim_pay",
                amount=refund_amount,
                reason=reason,
            )

            refund = Refund.objects.create(
                payment=payment,
                booking=payment.booking,
                amount=refund_amount,
                currency=payment.currency,
                reason=reason,
                status=PaymentStatus.SUCCESS,
                initiated_by=actor,
                gateway_refund_id=gateway_resp.get("gateway_refund_id", ""),
                gateway_response_payload=gateway_resp,
            )

            payment.status = PaymentStatus.REFUNDED
            payment.save()

            booking = payment.booking
            booking.refund_amount = max(booking.refund_amount, refund_amount)
            booking.status = BookingStatus.REFUNDED
            booking.save()

            AuditService.log_action(
                actor=actor,
                action="REFUND_PROCESSED",
                obj=refund,
                changes={"amount": str(refund_amount), "reason": reason},
            )

            try:
                NotificationService.notify_refund_processed(booking, refund, actor=actor)
            except Exception as e:
                logger.warning(f"Failed to dispatch refund notification for booking {booking.id}: {e}")

            return refund
