from django.db.models import Q
import uuid
import secrets
from datetime import datetime, timezone
from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel, UUIDModel
from apps.halls.models import Hall
from apps.availability.models import TimeSlot

class EventType(models.TextChoices):
    WEDDING = 'WEDDING', 'Wedding'
    RECEPTION = 'RECEPTION', 'Reception'
    ENGAGEMENT = 'ENGAGEMENT', 'Engagement Ceremony'
    BIRTHDAY = 'BIRTHDAY', 'Birthday Party'
    CORPORATE = 'CORPORATE', 'Corporate Event / Conference'
    ANNIVERSARY = 'ANNIVERSARY', 'Anniversary Celebration'
    OTHER = 'OTHER', 'Other Social Event'


class BookingStatus(models.TextChoices):
    PAYMENT_PENDING = 'PAYMENT_PENDING', 'Payment Pending'
    PENDING_OWNER_CONFIRMATION = 'PENDING_OWNER_CONFIRMATION', 'Pending Owner Confirmation'
    CONFIRMED = 'CONFIRMED', 'Confirmed'
    REJECTED = 'REJECTED', 'Declined by Owner'
    CANCELLED_BY_CUSTOMER = 'CANCELLED_BY_CUSTOMER', 'Cancelled by Customer'
    CANCELLED_BY_OWNER = 'CANCELLED_BY_OWNER', 'Cancelled by Owner'
    CANCELLED_BY_ADMIN = 'CANCELLED_BY_ADMIN', 'Cancelled by Admin'
    COMPLETED = 'COMPLETED', 'Completed'
    DISPUTED = 'DISPUTED', 'Disputed'
    REFUND_PENDING = 'REFUND_PENDING', 'Refund Pending'
    REFUNDED = 'REFUNDED', 'Refunded'


ACTIVE_BLOCKING_STATUSES = [
    BookingStatus.PENDING_OWNER_CONFIRMATION,
    BookingStatus.CONFIRMED,
    BookingStatus.COMPLETED,
    ]

BLOCKING_BOOKING_STATUSES = [
    BookingStatus.PENDING_OWNER_CONFIRMATION,
    BookingStatus.CONFIRMED,
    ]


class Booking(UUIDModel, TimeStampedModel):
    """
    Authoritative Booking Model with frozen financial calculations and state machine transitions.
    """
    booking_number = models.CharField(max_length=30, unique=True, db_index=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='bookings'
    )
    hall = models.ForeignKey(
        Hall,
        on_delete=models.PROTECT,
        related_name='bookings'
    )

    # Event Details
    event_type = models.CharField(max_length=50, choices=EventType.choices, default=EventType.WEDDING)
    event_date = models.DateField(db_index=True)
    time_slot = models.CharField(max_length=20, choices=TimeSlot.choices, db_index=True)
    guest_count = models.PositiveIntegerField()

    # Contact & Special Notes
    contact_name = models.CharField(max_length=150)
    contact_phone = models.CharField(max_length=20)
    special_requests = models.TextField(blank=True, default="")

    # Selected Add-ons
    has_catering = models.BooleanField(default=False)
    catering_plate_type = models.CharField(max_length=20, default="VEG")
    catering_plate_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    has_decor = models.BooleanField(default=False)
    has_dj = models.BooleanField(default=False)

    # Frozen Financial Values (Calculated server-side via PricingService)
    hall_rent = models.DecimalField(max_digits=12, decimal_places=2)
    catering_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    decor_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    dj_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18.00)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    # Advance & Balance Breakdown
    advance_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=20.00)
    advance_amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    # State Machine & Expiry
    status = models.CharField(
        max_length=35,
        choices=BookingStatus.choices,
        default=BookingStatus.PAYMENT_PENDING,
        db_index=True
    )
    owner_response_notes = models.TextField(blank=True, default="")
    cancellation_reason = models.TextField(blank=True, default="")
    cancellation_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = 'bookings'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['hall', 'event_date', 'time_slot']),
            models.Index(fields=['status', 'expires_at']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(guest_count__gt=0),
                name='chk_booking_guest_count_positive'
            ),
            models.CheckConstraint(
                condition=models.Q(total_amount__gte=0) & models.Q(advance_amount__gte=0) & models.Q(balance_amount__gte=0),
                name='chk_booking_amounts_positive'
            ),


            models.UniqueConstraint(
               fields=['hall', 'event_date', 'time_slot'],
               condition=Q(
               status__in=[

                BookingStatus.PENDING_OWNER_CONFIRMATION,
                BookingStatus.CONFIRMED,

              ]
              ),
            name='unique_active_booking_hall_date_slot',
            ),
        ]

        
   
    
    @classmethod
    def is_slot_available(cls, hall_id, event_date, time_slot):
        """
        Returns True if the hall/time slot is available.
        """

        blocking_booking_exists = cls.objects.filter(

           hall_id=hall_id,
           event_date=event_date,
        #    time_slot=time_slot,
           status__in=ACTIVE_BLOCKING_STATUSES,
        ).exists()

        return not blocking_booking_exists

    def save(self, *args, **kwargs):
        if not self.booking_number:
            year = datetime.now().year
            rand_suffix = secrets.token_hex(3).upper()
            self.booking_number = f"BK-{year}-{rand_suffix}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.booking_number} - {self.hall.name} on {self.event_date} ({self.status})"

    @property
    def is_fully_paid(self):
        return self.amount_paid >= self.total_amount

    @property
    def is_advance_paid(self):
        return self.amount_paid >= self.advance_amount
