import uuid
import secrets
from datetime import datetime, timezone
from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel, UUIDModel
from apps.bookings.models import Booking

class PayoutStatus(models.TextChoices):
    SCHEDULED = 'SCHEDULED', 'Scheduled'
    PROCESSING = 'PROCESSING', 'Processing'
    PAID = 'PAID', 'Paid Out'
    FAILED = 'FAILED', 'Failed'
    ON_HOLD = 'ON_HOLD', 'On Hold (Disputed)'


class Payout(UUIDModel, TimeStampedModel):
    """
    Authoritative record of owner earnings settlement and platform commission deductions.
    """
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='payouts'
    )
    booking = models.OneToOneField(
        Booking,
        on_delete=models.PROTECT,
        related_name='payout'
    )
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=PayoutStatus.choices,
        default=PayoutStatus.SCHEDULED,
        db_index=True
    )
    payout_date = models.DateField(db_index=True)
    transaction_reference = models.CharField(max_length=100, unique=True, db_index=True)
    gateway_payout_id = models.CharField(max_length=255, null=True, blank=True)
    failure_reason = models.TextField(blank=True, default="")

    class Meta:
        db_table = 'payouts'
        ordering = ['-payout_date', '-created_at']
        indexes = [
            models.Index(fields=['owner', 'status', 'payout_date']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(gross_amount__gte=0) & models.Q(net_amount__gte=0) & models.Q(commission_amount__gte=0),
                name='chk_payout_amounts_positive'
            )
        ]

    def save(self, *args, **kwargs):
        if not self.transaction_reference:
            year = datetime.now().year
            rand_suffix = secrets.token_hex(4).upper()
            self.transaction_reference = f"PO-{year}-{rand_suffix}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.transaction_reference} - {self.owner.email}: ₹{self.net_amount} ({self.status})"
