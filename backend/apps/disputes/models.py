from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel, UUIDModel
from apps.bookings.models import Booking

class DisputeStatus(models.TextChoices):
    OPEN = 'OPEN', 'Open'
    UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'
    RESOLVED = 'RESOLVED', 'Resolved'
    CLOSED = 'CLOSED', 'Closed'


class DisputeResolutionType(models.TextChoices):
    CUSTOMER_REFUND = 'CUSTOMER_REFUND', 'Full Customer Refund'
    PARTIAL_REFUND = 'PARTIAL_REFUND', 'Partial Customer Refund'
    OWNER_FAVORED = 'OWNER_FAVORED', 'Owner Favored (Claim Rejected)'
    NO_ACTION = 'NO_ACTION', 'No Action'


class Dispute(UUIDModel, TimeStampedModel):
    """
    Formal dispute case lodged by customer or owner regarding a booking.
    """
    booking = models.OneToOneField(
        Booking,
        on_delete=models.PROTECT,
        related_name='dispute'
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='opened_disputes'
    )
    reason = models.CharField(max_length=150)
    description = models.TextField()
    evidence_urls = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=30,
        choices=DisputeStatus.choices,
        default=DisputeStatus.OPEN,
        db_index=True
    )
    resolution_type = models.CharField(
        max_length=30,
        choices=DisputeResolutionType.choices,
        null=True,
        blank=True
    )
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    admin_notes = models.TextField(blank=True, default="")
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_disputes'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'disputes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"Dispute #{str(self.id)[:8]} on Booking #{self.booking.booking_number} ({self.status})"
