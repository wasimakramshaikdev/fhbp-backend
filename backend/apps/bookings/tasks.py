import logging
from datetime import datetime, timezone
from celery import shared_task
from django.db import transaction
from apps.bookings.models import Booking, BookingStatus
from apps.availability.services.availability import AvailabilityService
from apps.notifications.tasks import send_in_app_notification_task, send_email_notification_task
from apps.notifications.models import NotificationType

logger = logging.getLogger(__name__)

@shared_task
def expire_unpaid_holds():
    """
    Celery Beat task: Scans bookings with status PAYMENT_PENDING past expires_at (15 min TTL)
    and releases the held availability slots back to OPEN.
    """
    now_utc = datetime.now(timezone.utc)
    expired_bookings = Booking.objects.filter(
        status=BookingStatus.PAYMENT_PENDING,
        expires_at__lte=now_utc
    )

    count = 0
    for booking in expired_bookings:
        with transaction.atomic():
            locked = Booking.objects.select_for_update().filter(id=booking.id, status=BookingStatus.PAYMENT_PENDING).first()
            if locked:
                locked.status = BookingStatus.CANCELLED_BY_CUSTOMER
                locked.cancellation_reason = "15-minute checkout payment window expired."
                locked.save()

                # Release availability slot hold
                AvailabilityService.release_hold(
                    hall=locked.hall,
                    event_date=locked.event_date,
                    slot=locked.time_slot,
                    booking_id=locked.id
                )
                count += 1
                logger.info(f"Released expired booking hold for #{locked.booking_number} on {locked.event_date}")

    logger.info(f"Expired holds sweep completed. Released {count} expired holds.")
    return count


@shared_task
def auto_complete_past_events():
    """
    Celery Beat task: Scans confirmed bookings whose event date has concluded,
    transitions them to COMPLETED, and alerts the customer to leave a review.
    """
    today = datetime.now(timezone.utc).date()
    past_bookings = Booking.objects.filter(
        status=BookingStatus.CONFIRMED,
        event_date__lt=today
    )

    completed_count = 0
    for booking in past_bookings:
        with transaction.atomic():
            locked = Booking.objects.select_for_update().filter(id=booking.id, status=BookingStatus.CONFIRMED).first()
            if locked:
                locked.status = BookingStatus.COMPLETED
                locked.save()
                completed_count += 1

                # Send review prompt in-app
                send_in_app_notification_task.delay(
                    user_id=str(locked.customer.id),
                    title="How was your event? Leave a Review!",
                    message=f"Your event at {locked.hall.name} has concluded. Rate your experience to help future event planners.",
                    notification_type=NotificationType.EVENT_COMPLETED,
                    related_entity_type="Booking",
                    related_entity_id=str(locked.id)
                )

                # Send review prompt email
                send_email_notification_task.delay(
                    recipient_email=locked.customer.email,
                    subject=f"Rate your experience at {locked.hall.name}!",
                    body=f"Dear {locked.contact_name},\n\nWe hope your event on {locked.event_date} was wonderful! Please take a minute to leave a review on HallBook.\n\nHallBook Team"
                )

    logger.info(f"Auto-completed {completed_count} concluded events.")
    return completed_count
