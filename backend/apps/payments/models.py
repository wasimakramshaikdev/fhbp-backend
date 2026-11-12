import uuid
import secrets
from datetime import datetime, timezone
from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel, UUIDModel
from apps.bookings.models import Booking

class PaymentType(models.TextChoices):
    ADVANCE = 'ADVANCE', 'Advance Deposit'
    BALANCE = 'BALANCE', 'Balance Settlement'
    FULL = 'FULL', 'Full Payment'
    REFUND = 'REFUND', 'Refund'


class PaymentMethod(models.TextChoices):
    UPI = 'UPI', 'UPI / QR Code'
    CREDIT_CARD = 'CREDIT_CARD', 'Credit Card'
    DEBIT_CARD = 'DEBIT_CARD', 'Debit Card'
    NET_BANKING = 'NET_BANKING', 'Net Banking'


class PaymentStatus(models.TextChoices):
    INITIATED = 'INITIATED', 'Initiated'
    PENDING = 'PENDING', 'Pending'
    SUCCESS = 'SUCCESS', 'Success'
    FAILED = 'FAILED', 'Failed'
    REFUNDED = 'REFUNDED', 'Refunded'


class PaymentGatewayType(models.TextChoices):
    RAZORPAY = 'RAZORPAY', 'Razorpay'
    STRIPE = 'STRIPE', 'Stripe'
    SIMULATED = 'SIMULATED', 'Simulated Gateway'


class Payment(UUIDModel, TimeStampedModel):
    """
    Authoritative record of financial payment transactions.
    """
    booking = models.ForeignKey(
        Booking,
        on_delete=models.PROTECT,
        related_name='payments'
    )
    payment_reference = models.CharField(max_length=100, unique=True, db_index=True)
    idempotency_key = models.CharField(max_length=255, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='INR')
    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
        default=PaymentType.ADVANCE,
        db_index=True
    )
    payment_method = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.UPI
    )
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.INITIATED,
        db_index=True
    )
    gateway = models.CharField(
        max_length=30,
        choices=PaymentGatewayType.choices,
        default=PaymentGatewayType.SIMULATED
    )
    gateway_order_id = models.CharField(max_length=255, db_index=True)
    gateway_payment_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    gateway_signature = models.CharField(max_length=500, null=True, blank=True)
    gateway_response_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default="")
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['booking', 'status']),
            models.Index(fields=['gateway_order_id', 'gateway_payment_id']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name='chk_payment_amount_positive'
            )
        ]

    def save(self, *args, **kwargs):
        if not self.payment_reference:
            year = datetime.now().year
            rand_suffix = secrets.token_hex(4).upper()
            self.payment_reference = f"PAY-{year}-{rand_suffix}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.payment_reference} - ₹{self.amount} ({self.status})"


class Refund(UUIDModel, TimeStampedModel):
    """
    Independent audit record for issued refunds.
    """
    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name='refunds'
    )
    booking = models.ForeignKey(
        Booking,
        on_delete=models.PROTECT,
        related_name='refunds'
    )
    refund_reference = models.CharField(max_length=100, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='INR')
    reason = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.SUCCESS,
        db_index=True
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='initiated_refunds'
    )
    gateway_refund_id = models.CharField(max_length=255, null=True, blank=True)
    gateway_response_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'refunds'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.refund_reference:
            year = datetime.now().year
            rand_suffix = secrets.token_hex(4).upper()
            self.refund_reference = f"REF-{year}-{rand_suffix}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.refund_reference} - ₹{self.amount} ({self.status})"
