import uuid
from datetime import datetime, timezone
from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel, UUIDModel

class NotificationType(models.TextChoices):
    BOOKING_CREATED = 'BOOKING_CREATED', 'New Booking Request'
    BOOKING_CONFIRMED = 'BOOKING_CONFIRMED', 'Booking Confirmed'
    BOOKING_REJECTED = 'BOOKING_REJECTED', 'Booking Declined'
    BOOKING_CANCELLED = 'BOOKING_CANCELLED', 'Booking Cancelled'
    REFUND_PROCESSED = 'REFUND_PROCESSED', 'Refund Processed'
    PAYMENT_SUCCESS = 'PAYMENT_SUCCESS', 'Payment Received'
    BALANCE_DUE = 'BALANCE_DUE', 'Balance Payment Reminder'
    EVENT_REMINDER = 'EVENT_REMINDER', 'Upcoming Event Reminder'
    EVENT_COMPLETED = 'EVENT_COMPLETED', 'Event Completed & Review Prompt'
    HALL_APPROVED = 'HALL_APPROVED', 'Venue Listing Approved'
    HALL_REJECTED = 'HALL_REJECTED', 'Venue Listing Changes Requested'
    DISPUTE_OPENED = 'DISPUTE_OPENED', 'Dispute Opened'
    DISPUTE_RESOLVED = 'DISPUTE_RESOLVED', 'Dispute Resolved'
    PAYOUT_INITIATED = 'PAYOUT_INITIATED', 'Owner Payout Dispatched'


class Notification(UUIDModel, TimeStampedModel):
    """
    In-app multi-channel notification feed for users.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
        default=NotificationType.BOOKING_CREATED,
        db_index=True
    )
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    related_entity_type = models.CharField(max_length=50, blank=True, default="")
    related_entity_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', 'created_at']),
        ]

    def __str__(self):
        return f"[{self.type}] To: {self.user.email} - {self.title}"

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.now(timezone.utc)
            self.save(update_fields=['is_read', 'read_at'])
