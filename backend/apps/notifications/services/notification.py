import logging
from apps.notifications.tasks import send_email_notification_task, send_in_app_notification_task
from apps.notifications.models import NotificationType

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    def _dispatch_async(task, **kwargs):
        return task.apply_async(kwargs=kwargs, queue='emails')

    @staticmethod
    def notify_booking_created(booking):
        """Alerts the hall owner that a new reservation request has been submitted."""
        owner = booking.hall.owner
        title = f"New Booking Request: #{booking.booking_number}"
        msg = f"{booking.contact_name} has requested {booking.hall.name} for {booking.event_date} ({booking.time_slot}) for {booking.guest_count} guests."
        
        NotificationService._dispatch_async(
            send_in_app_notification_task,
            user_id=str(owner.id),
            title=title,
            message=msg,
            notification_type=NotificationType.BOOKING_CREATED,
            related_entity_type="Booking",
            related_entity_id=str(booking.id)
        )
        NotificationService._dispatch_async(
            send_email_notification_task,
            recipient_email=owner.email,
            subject=f"Action Required: New Booking Request for {booking.hall.name}",
            body=f"Hello,\n\nYou have received a new booking request for {booking.hall.name}.\nEvent Date: {booking.event_date}\nSlot: {booking.time_slot}\nGuests: {booking.guest_count}\n\nPlease review and confirm in your HallBook Owner Dashboard.\n\nHallBook Team"
        )

    @staticmethod
    def notify_booking_confirmed(booking):
        """Alerts the customer that the hall owner has accepted their booking."""
        customer = booking.customer
        title = f"Booking Confirmed: #{booking.booking_number}!"
        msg = f"Great news! The owner of {booking.hall.name} has confirmed your event on {booking.event_date} ({booking.time_slot})."

        NotificationService._dispatch_async(
            send_in_app_notification_task,
            user_id=str(customer.id),
            title=title,
            message=msg,
            notification_type=NotificationType.BOOKING_CONFIRMED,
            related_entity_type="Booking",
            related_entity_id=str(booking.id)
        )
        NotificationService._dispatch_async(
            send_email_notification_task,
            recipient_email=customer.email,
            subject=f"Booking Confirmed: {booking.hall.name} on {booking.event_date}",
            body=f"Dear {booking.contact_name},\n\nYour function hall reservation at {booking.hall.name} for {booking.event_date} ({booking.time_slot}) is officially confirmed!\n\nHallBook Team"
        )

    @staticmethod
    def notify_booking_rejected(booking, reason: str = ""):
        """Alerts the customer that the hall owner declined their request."""
        customer = booking.customer
        title = f"Booking Declined: #{booking.booking_number}"
        msg = f"The owner of {booking.hall.name} was unable to accept your request for {booking.event_date}. Reason: {reason or 'Unavailable'}. Your 100% advance has been refunded."

        NotificationService._dispatch_async(
            send_in_app_notification_task,
            user_id=str(customer.id),
            title=title,
            message=msg,
            notification_type=NotificationType.BOOKING_REJECTED,
            related_entity_type="Booking",
            related_entity_id=str(booking.id)
        )
        NotificationService._dispatch_async(
            send_email_notification_task,
            recipient_email=customer.email,
            subject=f"Booking Update: #{booking.booking_number}",
            body=f"Dear {booking.contact_name},\n\nUnfortunately, {booking.hall.name} could not accept your booking for {booking.event_date}.\nReason: {reason or 'Unavailable'}\n\nYour 100% advance deposit has been refunded to your original payment method.\n\nHallBook Team"
        )

    @staticmethod
    def notify_booking_cancelled(booking, actor, reason: str = ""):
        """Alerts both customer and hall owner that a booking has been cancelled."""
        customer = booking.customer
        owner = booking.hall.owner
        cancelled_by = "you" if customer == actor else "the hall owner" if owner == actor else "the booking party"
        refund_text = f"A refund of ₹{booking.refund_amount} has been initiated." if booking.refund_amount > 0 else "No refund is due for this cancellation."

        customer_title = f"Booking Cancelled: #{booking.booking_number}"
        customer_msg = (
            f"Your booking at {booking.hall.name} for {booking.event_date} ({booking.time_slot}) has been cancelled."
            f" {refund_text}"
        )
        if reason:
            customer_msg += f" Reason: {reason}"

        owner_title = f"Booking Cancelled: #{booking.booking_number}"
        owner_msg = (
            f"The booking for {booking.hall.name} on {booking.event_date} ({booking.time_slot}) was cancelled by {cancelled_by}."
            f" {refund_text}"
        )
        if reason:
            owner_msg += f" Reason: {reason}"

        for user, title, message in [
            (customer, customer_title, customer_msg),
            (owner, owner_title, owner_msg),
        ]:
            NotificationService._dispatch_async(
                send_in_app_notification_task,
                user_id=str(user.id),
                title=title,
                message=message,
                notification_type=NotificationType.BOOKING_CANCELLED,
                related_entity_type="Booking",
                related_entity_id=str(booking.id)
            )
            NotificationService._dispatch_async(
                send_email_notification_task,
                recipient_email=user.email,
                subject=f"Booking Cancelled: #{booking.booking_number} | {booking.hall.name}",
                body=(
                    f"Dear {user.full_name or 'Guest'},\n\n"
                    f"Your booking at {booking.hall.name} for {booking.event_date} ({booking.time_slot}) has been cancelled.\n"
                    f"{refund_text}\n"
                    f"{('Reason: ' + reason) if reason else ''}\n\n"
                    "HallBook Team"
                ).strip()
            )

    @staticmethod
    def notify_refund_processed(booking, refund, actor=None):
        """Alerts both parties that a refund has been processed."""
        customer = booking.customer
        owner = booking.hall.owner

        for user, label in [(customer, "Customer"), (owner, "Hall Owner")]:
            title = f"Refund Processed: #{booking.booking_number}"
            message = (
                f"A refund of ₹{refund.amount} for booking #{booking.booking_number} has been processed for the {label.lower()}"
                f" on {booking.event_date}."
            )
            NotificationService._dispatch_async(
                send_in_app_notification_task,
                user_id=str(user.id),
                title=title,
                message=message,
                notification_type=NotificationType.REFUND_PROCESSED,
                related_entity_type="Refund",
                related_entity_id=str(refund.id)
            )
            NotificationService._dispatch_async(
                send_email_notification_task,
                recipient_email=user.email,
                subject=f"Refund Processed: #{booking.booking_number}",
                body=(
                    f"Dear {user.full_name or label},\n\n"
                    f"Refund of ₹{refund.amount} for booking #{booking.booking_number} has been processed.\n"
                    f"Hall: {booking.hall.name}\n"
                    f"Event Date: {booking.event_date}\n\n"
                    "HallBook Team"
                )
            )

    @staticmethod
    def notify_payment_success(payment):
        """Alerts the customer of successful payment receipt."""
        customer = payment.booking.customer
        title = f"Payment Successful: {payment.payment_reference}"
        msg = f"Your payment of ₹{payment.amount} for booking #{payment.booking.booking_number} was successfully processed."

        NotificationService._dispatch_async(
            send_in_app_notification_task,
            user_id=str(customer.id),
            title=title,
            message=msg,
            notification_type=NotificationType.PAYMENT_SUCCESS,
            related_entity_type="Payment",
            related_entity_id=str(payment.id)
        )
        NotificationService._dispatch_async(
            send_email_notification_task,
            recipient_email=customer.email,
            subject=f"Payment Receipt: #{payment.payment_reference} (₹{payment.amount})",
            body=f"Dear Customer,\n\nWe have received your payment of ₹{payment.amount} for {payment.booking.hall.name}.\nYou can view and download your official GST tax invoice in your dashboard.\n\nHallBook Team"
        )

    notify_payment_received = notify_payment_success
