import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from django.db import transaction
from apps.core.services.audit import AuditService
from apps.halls.models import Hall, HallApprovalStatus, HallStatus, CancellationPolicy
from apps.availability.models import TimeSlot
from apps.availability.services.availability import AvailabilityService, AvailabilityConflictError
from apps.bookings.models import Booking, BookingStatus, EventType
from apps.bookings.services.pricing import PricingService
from apps.payments.models import PaymentStatus
from apps.payments.services.payment import PaymentService

class BookingValidationError(Exception):
    pass

class BookingService:
    @classmethod
    def create_booking_intent(
        cls,
        customer,
        hall: Hall,
        event_date,
        time_slot: str,
        guest_count: int,
        contact_name: str,
        contact_phone: str,
        special_requests: str = "",
        has_catering: bool = False,
        catering_type: str = 'VEG',
        has_decor: bool = False,
        has_dj: bool = False,
        event_type: str = EventType.WEDDING,
    ) -> Booking:
        """
        Creates a new booking intent in atomic transaction with pessimistic availability locking.
        """
        # 1. Validate Hall Status
        if hall.approval_status != HallApprovalStatus.APPROVED or hall.status != HallStatus.ACTIVE:
            raise BookingValidationError("This function hall is currently not active for bookings.")

        # 2. Validate Capacity
        if guest_count < hall.min_capacity:
            raise BookingValidationError(f"Guest count ({guest_count}) is below minimum capacity ({hall.min_capacity}).")
        if guest_count > hall.max_capacity:
            raise BookingValidationError(f"Guest count ({guest_count}) exceeds maximum capacity ({hall.max_capacity}).")

        # 3. Calculate Frozen Price Server-Side
        quote = PricingService.calculate_quote(
            hall=hall,
            slot=time_slot,
            guest_count=guest_count,
            has_catering=has_catering,
            catering_type=catering_type,
            has_decor=has_decor,
            has_dj=has_dj,
        )

        now_utc = datetime.now(timezone.utc)
        expires_at = now_utc + timedelta(minutes=15)

        with transaction.atomic():
            # Check if active unexpired booking intent already exists for this customer/hall/date/slot
            existing_booking = Booking.objects.select_for_update().filter(
                customer=customer,
                hall=hall,
                event_date=event_date,
                time_slot=time_slot,
                status=BookingStatus.PAYMENT_PENDING,
                expires_at__gt=now_utc
            ).first()

            booking_id = existing_booking.id if existing_booking else uuid.uuid4()

            # 4. Acquire Row-Level Lock and Hold Slot
            try:
                AvailabilityService.hold_slot_atomic(
                    hall=hall,
                    event_date=event_date,
                    slot=time_slot,
                    booking_id=booking_id,
                    duration_minutes=15
                )
            except AvailabilityConflictError as exc:
                raise BookingValidationError(str(exc))

            if existing_booking:
                # Update existing booking intent in place
                existing_booking.event_type = event_type
                existing_booking.guest_count = guest_count
                existing_booking.contact_name = contact_name
                existing_booking.contact_phone = contact_phone
                existing_booking.special_requests = special_requests
                existing_booking.has_catering = has_catering
                existing_booking.catering_plate_type = catering_type
                existing_booking.catering_plate_price = quote['per_plate_price']
                existing_booking.has_decor = has_decor
                existing_booking.has_dj = has_dj
                existing_booking.hall_rent = quote['hall_rent']
                existing_booking.catering_amount = quote['catering_amount']
                existing_booking.decor_amount = quote['decor_amount']
                existing_booking.dj_amount = quote['dj_amount']
                existing_booking.subtotal = quote['subtotal']
                existing_booking.discount_amount = quote['discount_amount']
                existing_booking.tax_rate = quote['tax_rate']
                existing_booking.tax_amount = quote['tax_amount']
                existing_booking.total_amount = quote['total_amount']
                existing_booking.advance_percentage = quote['advance_percentage']
                existing_booking.advance_amount = quote['advance_amount']
                existing_booking.balance_amount = quote['balance_amount']
                existing_booking.expires_at = expires_at
                existing_booking.save()
                booking = existing_booking
            else:
                # 5. Create New Booking Record
                booking = Booking.objects.create(
                    id=booking_id,
                    customer=customer,
                    hall=hall,
                    event_type=event_type,
                    event_date=event_date,
                    time_slot=time_slot,
                    guest_count=guest_count,
                    contact_name=contact_name,
                    contact_phone=contact_phone,
                    special_requests=special_requests,
                    has_catering=has_catering,
                    catering_plate_type=catering_type,
                    catering_plate_price=quote['per_plate_price'],
                    has_decor=has_decor,
                    has_dj=has_dj,
                    hall_rent=quote['hall_rent'],
                    catering_amount=quote['catering_amount'],
                    decor_amount=quote['decor_amount'],
                    dj_amount=quote['dj_amount'],
                    subtotal=quote['subtotal'],
                    discount_amount=quote['discount_amount'],
                    tax_rate=quote['tax_rate'],
                    tax_amount=quote['tax_amount'],
                    total_amount=quote['total_amount'],
                    advance_percentage=quote['advance_percentage'],
                    advance_amount=quote['advance_amount'],
                    balance_amount=quote['balance_amount'],
                    amount_paid=Decimal('0.00'),
                    status=BookingStatus.PAYMENT_PENDING,
                    expires_at=expires_at
                )

            AuditService.log_action(
                actor=customer,
                action="BOOKING_INTENT_CREATED",
                obj=booking,
                changes={"total": str(booking.total_amount), "advance": str(booking.advance_amount)}
            )

            # Trigger Owner Notification
            from apps.notifications.services.notification import NotificationService
            NotificationService.notify_booking_created(booking)

            return booking

    @classmethod
    def owner_accept_booking(cls, booking: Booking, owner, notes: str = "") -> Booking:
        """Owner accepts a pending booking request."""
        with transaction.atomic():
            locked_booking = Booking.objects.select_for_update().get(id=booking.id)
            if locked_booking.hall.owner != owner and not owner.is_admin:
                raise BookingValidationError("You do not have permission to accept this booking.")

            if locked_booking.status != BookingStatus.PENDING_OWNER_CONFIRMATION:
                raise BookingValidationError(f"Cannot accept booking in '{locked_booking.status}' status.")

            locked_booking.status = BookingStatus.CONFIRMED
            locked_booking.owner_response_notes = notes
            locked_booking.save()

            # Permanently confirm slot as booked
            AvailabilityService.confirm_slot_booked(
                hall=locked_booking.hall,
                event_date=locked_booking.event_date,
                slot=locked_booking.time_slot,
                booking_id=locked_booking.id
            )

            AuditService.log_action(
                actor=owner,
                action="OWNER_ACCEPTED_BOOKING",
                obj=locked_booking,
                changes={"status": "CONFIRMED", "notes": notes}
            )

            from apps.notifications.services.notification import NotificationService
            NotificationService.notify_booking_confirmed(locked_booking)

            # Schedule Payout for owner
            from apps.payouts.services.payout import PayoutService
            PayoutService.schedule_payout_for_booking(locked_booking)

            return locked_booking

    @classmethod
    def owner_reject_booking(cls, booking: Booking, owner, reason: str = "") -> Booking:
        """Owner rejects a pending booking request."""
        with transaction.atomic():
            locked_booking = Booking.objects.select_for_update().get(id=booking.id)
            if locked_booking.hall.owner != owner and not owner.is_admin:
                raise BookingValidationError("You do not have permission to decline this booking.")

            if locked_booking.status != BookingStatus.PENDING_OWNER_CONFIRMATION:
                raise BookingValidationError(f"Cannot decline booking in '{locked_booking.status}' status.")

            locked_booking.status = BookingStatus.REJECTED
            locked_booking.owner_response_notes = reason
            locked_booking.refund_amount = locked_booking.amount_paid
            locked_booking.save()

            # Release slot hold
            AvailabilityService.release_hold(
                hall=locked_booking.hall,
                event_date=locked_booking.event_date,
                slot=locked_booking.time_slot,
                booking_id=locked_booking.id
            )

            AuditService.log_action(
                actor=owner,
                action="OWNER_REJECTED_BOOKING",
                obj=locked_booking,
                changes={"status": "REJECTED", "reason": reason, "refund_amount": str(locked_booking.refund_amount)}
            )

            from apps.notifications.services.notification import NotificationService
            NotificationService.notify_booking_rejected(locked_booking, reason=reason)

            return locked_booking

    @classmethod
    def process_booking_refund(cls, booking: Booking, actor, reason: str = "", amount: Decimal = None) -> Booking:
        """Processes a real payment refund for a cancelled booking when the owner/admin approves it."""
        with transaction.atomic():
            locked_booking = Booking.objects.select_for_update().get(id=booking.id)
            is_owner = locked_booking.hall.owner == actor
            is_admin = getattr(actor, 'is_admin', False)

            if not (is_owner or is_admin):
                raise BookingValidationError("Only the hall owner or an admin can refund this booking.")

            if is_owner and locked_booking.status == BookingStatus.CANCELLED_BY_CUSTOMER:
                deadline = locked_booking.updated_at + timedelta(hours=24)
                if datetime.now(timezone.utc) > deadline:
                    raise BookingValidationError("Refunds for customer cancellations must be processed within 24 hours.")

            successful_payment = locked_booking.payments.filter(status=PaymentStatus.SUCCESS).order_by('-paid_at').first()
            if not successful_payment:
                raise BookingValidationError("No successful payment exists to refund for this booking.")

            refund_amount = amount or locked_booking.refund_amount or successful_payment.amount
            refund_amount = PricingService.quantize(refund_amount)
            if refund_amount <= Decimal('0.00'):
                raise BookingValidationError("Refund amount must be greater than zero.")

            PaymentService.execute_refund(
                payment_id=str(successful_payment.id),
                amount=refund_amount,
                reason=reason or "Refund processed for booking cancellation.",
                actor=actor,
            )

            locked_booking.refresh_from_db()
            return locked_booking

    @classmethod
    def cancel_booking(cls, booking: Booking, actor, reason: str = "") -> Booking:
        """Handles cancellation by customer or owner."""
        with transaction.atomic():
            locked_booking = Booking.objects.select_for_update().get(id=booking.id)
            is_customer = locked_booking.customer == actor
            is_owner = locked_booking.hall.owner == actor
            is_admin = getattr(actor, 'is_admin', False)

            if not (is_customer or is_owner or is_admin):
                raise BookingValidationError("Permission denied to cancel this booking.")

            if locked_booking.status in [BookingStatus.COMPLETED, BookingStatus.CANCELLED_BY_CUSTOMER, BookingStatus.CANCELLED_BY_OWNER]:
                raise BookingValidationError(f"Cannot cancel booking in '{locked_booking.status}' status.")

            # Calculate refund based on the event-time-to-cancel window.
            # Rules:
            # - > 90 days out: 90% refund
            # - 30 to 90 days out: 50% refund
            # - < 30 days out: 0% refund
            # - Owner/admin-initiated cancellation: 100% refund immediately
            days_until_event = (locked_booking.event_date - datetime.now().date()).days
            policy = locked_booking.hall.cancellation_policy

            refund_pct = Decimal('0.00')
            if is_owner or is_admin:
                refund_pct = Decimal('100.00')
            else:
                if days_until_event > 90:
                    refund_pct = Decimal('90.00')
                elif days_until_event >= 30:
                    refund_pct = Decimal('50.00')
                else:
                    refund_pct = Decimal('0.00')

                # Preserve hall-specific policy values if a venue chooses a tighter policy.
                if policy == CancellationPolicy.FLEXIBLE and days_until_event > 90:
                    refund_pct = Decimal('90.00')
                elif policy == CancellationPolicy.MODERATE and days_until_event >= 30:
                    refund_pct = Decimal('50.00')
                elif policy == CancellationPolicy.STRICT and days_until_event >= 30:
                    refund_pct = Decimal('50.00')
                elif policy == CancellationPolicy.STRICT and days_until_event < 30:
                    refund_pct = Decimal('0.00')

            refund_amount = PricingService.quantize(locked_booking.amount_paid * (refund_pct / Decimal('100.00')))
            cancellation_fee = locked_booking.amount_paid - refund_amount

            target_status = BookingStatus.CANCELLED_BY_CUSTOMER if is_customer else BookingStatus.CANCELLED_BY_OWNER

            locked_booking.status = target_status
            locked_booking.cancellation_reason = reason
            locked_booking.refund_amount = refund_amount
            locked_booking.cancellation_fee = cancellation_fee
            locked_booking.save()

            # Release slot
            AvailabilityService.release_hold(
                hall=locked_booking.hall,
                event_date=locked_booking.event_date,
                slot=locked_booking.time_slot,
                booking_id=locked_booking.id
            )

            AuditService.log_action(
                actor=actor,
                action="BOOKING_CANCELLED",
                obj=locked_booking,
                changes={"status": target_status, "refund_amount": str(refund_amount)}
            )

            from apps.notifications.services.notification import NotificationService
            NotificationService.notify_booking_cancelled(locked_booking, actor=actor, reason=reason)

            return locked_booking
