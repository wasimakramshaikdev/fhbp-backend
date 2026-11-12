import calendar
from datetime import date as DateType, datetime, timedelta, timezone
from django.db import transaction, IntegrityError, OperationalError
from django.db.models import Q
from apps.availability.models import HallSlotAvailability, TimeSlot, SlotStatus
from apps.halls.models import Hall

class AvailabilityConflictError(Exception):
    pass

class AvailabilityService:
    @staticmethod
    def get_mutually_exclusive_slots(slot: str) -> list[str]:
        """Returns list of slot names that conflict with the requested slot."""
        if slot == TimeSlot.FULL_DAY:
            return [TimeSlot.FULL_DAY, TimeSlot.MORNING, TimeSlot.EVENING]
        elif slot in [TimeSlot.MORNING, TimeSlot.EVENING]:
            return [slot, TimeSlot.FULL_DAY]
        return [slot]

    @staticmethod
    def is_slot_open(slot_obj: HallSlotAvailability) -> bool:
        """Determines if a slot is currently bookable, accounting for hold expirations."""
        if not slot_obj:
            return True
        if slot_obj.status == SlotStatus.OPEN:
            return True
        if slot_obj.status == SlotStatus.HELD:
            # Check if hold expired
            if slot_obj.held_until and slot_obj.held_until <= datetime.now(timezone.utc):
                return True
        return False

    @classmethod
    def get_month_matrix(cls, hall: Hall, year: int, month: int) -> dict:
        """
        Returns full month calendar matrix with morning, evening, full_day availability for each day.
        """
        num_days = calendar.monthrange(year, month)[1]
        start_date = DateType(year, month, 1)
        end_date = DateType(year, month, num_days)

        existing_slots = HallSlotAvailability.objects.filter(
            hall=hall,
            date__range=[start_date, end_date]
        )
        slot_map = {(s.date, s.slot): s for s in existing_slots}

        matrix = {}
        now_utc = datetime.now(timezone.utc)

        for day in range(1, num_days + 1):
            curr_date = DateType(year, month, day)
            date_str = curr_date.isoformat()
            
            day_slots = {}
            for slot_type in [TimeSlot.MORNING, TimeSlot.EVENING, TimeSlot.FULL_DAY]:
                slot_obj = slot_map.get((curr_date, slot_type))
                
                status_val = SlotStatus.OPEN
                held_until_val = None
                blocked_reason_val = ""

                if slot_obj:
                    if slot_obj.status == SlotStatus.HELD and slot_obj.held_until and slot_obj.held_until > now_utc:
                        status_val = SlotStatus.HELD
                        held_until_val = slot_obj.held_until.isoformat()
                    elif slot_obj.status in [SlotStatus.BOOKED, SlotStatus.BLOCKED]:
                        status_val = slot_obj.status
                        blocked_reason_val = slot_obj.blocked_reason

                day_slots[slot_type] = {
                    "status": status_val,
                    "held_until": held_until_val,
                    "blocked_reason": blocked_reason_val,
                }

            # Check mutual exclusivity for composite display
            is_full_day_booked = day_slots[TimeSlot.FULL_DAY]["status"] == SlotStatus.BOOKED
            is_full_day_blocked = day_slots[TimeSlot.FULL_DAY]["status"] == SlotStatus.BLOCKED

            if is_full_day_booked:
                day_slots[TimeSlot.MORNING]["status"] = SlotStatus.BOOKED
                day_slots[TimeSlot.EVENING]["status"] = SlotStatus.BOOKED
            elif is_full_day_blocked:
                if day_slots[TimeSlot.MORNING]["status"] == SlotStatus.OPEN:
                    day_slots[TimeSlot.MORNING]["status"] = SlotStatus.BLOCKED
                if day_slots[TimeSlot.EVENING]["status"] == SlotStatus.OPEN:
                    day_slots[TimeSlot.EVENING]["status"] = SlotStatus.BLOCKED

            matrix[date_str] = day_slots

        return matrix

    @classmethod
    def check_availability(cls, hall: Hall, event_date: DateType, slot: str) -> dict:
        """
        Validates whether a specific date and time slot is available for booking.
        """
        conflicting_slots = cls.get_mutually_exclusive_slots(slot)
        records = HallSlotAvailability.objects.filter(
            hall=hall,
            date=event_date,
            slot__in=conflicting_slots
        )

        now_utc = datetime.now(timezone.utc)
        for rec in records:
            if rec.status == SlotStatus.BOOKED:
                return {
                    "is_available": False,
                    "status": SlotStatus.BOOKED,
                    "reason": f"Selected slot '{slot}' is already booked on {event_date}."
                }
            if rec.status == SlotStatus.BLOCKED:
                return {
                    "is_available": False,
                    "status": SlotStatus.BLOCKED,
                    "reason": f"Selected slot '{slot}' has been blocked by the venue owner ({rec.blocked_reason or 'Unavailable'})."
                }
            if rec.status == SlotStatus.HELD and rec.held_until and rec.held_until > now_utc:
                return {
                    "is_available": False,
                    "status": SlotStatus.HELD,
                    "reason": f"Selected slot '{slot}' is temporarily reserved by another customer. Please try again shortly."
                }

        return {
            "is_available": True,
            "status": SlotStatus.OPEN,
            "reason": "Slot is available."
        }

    @classmethod
    def hold_slot_atomic(cls, hall: Hall, event_date: DateType, slot: str, booking_id=None, duration_minutes=15):
        """
        Pessimistic concurrency lock:
        Locks the relevant rows via `select_for_update()`, verifies availability,
        and transitions the slot to HELD.
        """
        conflicting_slots = cls.get_mutually_exclusive_slots(slot)
        now_utc = datetime.now(timezone.utc)
        expires_at = now_utc + timedelta(minutes=duration_minutes)

        try:
            with transaction.atomic():
                # 1. Ensure the slot row exists so PostgreSQL row locking can lock it
                target_slot, created = HallSlotAvailability.objects.get_or_create(
                    hall=hall,
                    date=event_date,
                    slot=slot,
                    defaults={'status': SlotStatus.OPEN}
                )

                # 2. Acquire row-level lock on all conflicting slots
                locked_slots = list(HallSlotAvailability.objects.select_for_update().filter(
                    hall=hall,
                    date=event_date,
                    slot__in=conflicting_slots
                ))

                slot_dict = {s.slot: s for s in locked_slots}

                # 3. Check if any conflicting slot is booked, blocked, or currently held
                for rec in locked_slots:
                    if rec.status == SlotStatus.BOOKED:
                        raise AvailabilityConflictError(f"Slot {slot} on {event_date} is already booked.")
                    if rec.status == SlotStatus.BLOCKED:
                        raise AvailabilityConflictError(f"Slot {slot} on {event_date} is blocked by owner.")
                    if rec.status == SlotStatus.HELD and rec.held_until and rec.held_until > now_utc and rec.booking_id != booking_id:
                        raise AvailabilityConflictError(f"Slot {slot} on {event_date} is currently held by another checkout session.")

                target_slot = slot_dict.get(slot, target_slot)
                target_slot.status = SlotStatus.HELD
                target_slot.booking_id = booking_id
                target_slot.held_until = expires_at
                target_slot.lock_version += 1
                target_slot.save()

                return target_slot
        except (IntegrityError, OperationalError):
            raise AvailabilityConflictError(f"Slot {slot} on {event_date} was just claimed by another session.")

    @classmethod
    def confirm_slot_booked(cls, hall: Hall, event_date: DateType, slot: str, booking_id):
        """
        Permanently transitions slot status to BOOKED.
        """
        with transaction.atomic():
            conflicting_slots = cls.get_mutually_exclusive_slots(slot)
            
            # If FULL_DAY, mark all 3 slots as BOOKED
            if slot == TimeSlot.FULL_DAY:
                for s in [TimeSlot.FULL_DAY, TimeSlot.MORNING, TimeSlot.EVENING]:
                    rec, created = HallSlotAvailability.objects.select_for_update().get_or_create(
                        hall=hall,
                        date=event_date,
                        slot=s
                    )
                    rec.status = SlotStatus.BOOKED
                    rec.booking_id = booking_id
                    rec.held_until = None
                    rec.save()
            else:
                rec, created = HallSlotAvailability.objects.select_for_update().get_or_create(
                    hall=hall,
                    date=event_date,
                    slot=slot
                )
                rec.status = SlotStatus.BOOKED
                rec.booking_id = booking_id
                rec.held_until = None
                rec.save()

    @classmethod
    def release_hold(cls, hall: Hall, event_date: DateType, slot: str, booking_id=None):
        """Releases a temporary hold back to OPEN."""
        with transaction.atomic():
            query = Q(hall=hall, date=event_date, slot=slot, status=SlotStatus.HELD)
            if booking_id:
                query &= Q(booking_id=booking_id)

            slots = HallSlotAvailability.objects.filter(query)
            for s in slots:
                s.status = SlotStatus.OPEN
                s.booking_id = None
                s.held_until = None
                s.save()

    @classmethod
    def block_slot_manually(cls, hall: Hall, event_date: DateType, slot: str, reason: str = ""):
        """Owner blocks date/slot manually."""
        with transaction.atomic():
            rec, created = HallSlotAvailability.objects.select_for_update().get_or_create(
                hall=hall,
                date=event_date,
                slot=slot
            )
            if rec.status == SlotStatus.BOOKED:
                raise AvailabilityConflictError("Cannot block a slot that has an active confirmed booking.")

            rec.status = SlotStatus.BLOCKED
            rec.blocked_reason = reason or "Maintenance / Private Event"
            rec.held_until = None
            rec.booking_id = None
            rec.save()
            return rec

    @classmethod
    def unblock_slot_manually(cls, hall: Hall, event_date: DateType, slot: str):
        """Owner unblocks a manually blocked slot."""
        with transaction.atomic():
            rec = HallSlotAvailability.objects.select_for_update().filter(
                hall=hall,
                date=event_date,
                slot=slot
            ).first()
            if not rec:
                return None
            if rec.status == SlotStatus.BOOKED:
                raise AvailabilityConflictError("Cannot unblock a booked slot.")

            rec.status = SlotStatus.OPEN
            rec.blocked_reason = ""
            rec.save()
            return rec
