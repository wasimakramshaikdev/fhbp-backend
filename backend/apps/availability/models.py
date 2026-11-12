import uuid
from datetime import datetime, timezone
from django.db import models
from apps.core.models import TimeStampedModel, UUIDModel
from apps.halls.models import Hall

class TimeSlot(models.TextChoices):
    MORNING = 'MORNING', 'Morning (08:00 - 14:00)'
    EVENING = 'EVENING', 'Evening (16:00 - 23:00)'
    FULL_DAY = 'FULL_DAY', 'Full Day (08:00 - 23:00)'


class SlotStatus(models.TextChoices):
    OPEN = 'OPEN', 'Open'
    BOOKED = 'BOOKED', 'Booked'
    BLOCKED = 'BLOCKED', 'Blocked by Owner'
    HELD = 'HELD', 'Temporary Payment Hold'


class HallSlotAvailability(UUIDModel, TimeStampedModel):
    """
    Authoritative date & slot availability status for function halls.
    """
    hall = models.ForeignKey(
        Hall,
        on_delete=models.CASCADE,
        related_name='slot_availabilities'
    )
    date = models.DateField(db_index=True)
    slot = models.CharField(
        max_length=20,
        choices=TimeSlot.choices,
        db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=SlotStatus.choices,
        default=SlotStatus.OPEN,
        db_index=True
    )
    booking_id = models.UUIDField(null=True, blank=True, db_index=True)
    held_until = models.DateTimeField(null=True, blank=True)
    blocked_reason = models.CharField(max_length=255, blank=True, default="")
    lock_version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = 'hall_slot_availabilities'
        ordering = ['date', 'slot']
        indexes = [
            models.Index(fields=['hall', 'date', 'status']),
            models.Index(fields=['date', 'status']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['hall', 'date', 'slot'],
                name='unique_hall_date_slot'
            )
        ]

    def __str__(self):
        return f"{self.hall.name} - {self.date} [{self.slot}] -> {self.status}"

    @property
    def is_currently_held(self):
        if self.status == SlotStatus.HELD:
            if self.held_until and self.held_until > datetime.now(timezone.utc):
                return True
        return False

    @property
    def is_available(self):
        if self.status == SlotStatus.OPEN:
            return True
        if self.status == SlotStatus.HELD and self.held_until and self.held_until <= datetime.now(timezone.utc):
            return True # Hold expired
        return False
