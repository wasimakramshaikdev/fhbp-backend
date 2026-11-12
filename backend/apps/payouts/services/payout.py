from datetime import datetime, timedelta, timezone
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from apps.core.models import PlatformSetting
from apps.core.services.audit import AuditService
from apps.bookings.models import Booking, BookingStatus
from apps.payouts.models import Payout, PayoutStatus

class PayoutService:
    @staticmethod
    def get_platform_commission_rate() -> Decimal:
        """Retrieves configured commission rate from database, defaulting to 10.00%."""
        setting = PlatformSetting.objects.filter(key="PLATFORM_COMMISSION_PCT").first()
        if setting and isinstance(setting.value, dict) and "percentage" in setting.value:
            return Decimal(str(setting.value["percentage"]))
        return Decimal('10.00')

    @classmethod
    def schedule_payout_for_booking(cls, booking: Booking) -> Payout:
        """
        Creates or updates a scheduled payout for a completed/confirmed booking.
        """
        commission_rate = cls.get_platform_commission_rate()
        gross = booking.amount_paid
        commission_amount = (gross * (commission_rate / Decimal('100.00'))).quantize(Decimal('0.01'))
        net_amount = gross - commission_amount

        # Scheduled for 3 days post-event date
        payout_date = booking.event_date + timedelta(days=3)

        with transaction.atomic():
            payout, created = Payout.objects.select_for_update().get_or_create(
                booking=booking,
                defaults={
                    "owner": booking.hall.owner,
                    "gross_amount": gross,
                    "commission_rate": commission_rate,
                    "commission_amount": commission_amount,
                    "net_amount": net_amount,
                    "status": PayoutStatus.SCHEDULED,
                    "payout_date": payout_date,
                }
            )

            if not created:
                payout.gross_amount = gross
                payout.commission_amount = commission_amount
                payout.net_amount = net_amount
                payout.payout_date = payout_date
                payout.save()

            return payout

    @classmethod
    def get_owner_earnings_summary(cls, owner) -> dict:
        """
        Calculates high-level earnings and commission summaries for venue owner dashboard.
        Strictly READ-ONLY query with zero database writes.
        """
        payouts = Payout.objects.filter(owner=owner).select_related('booking', 'booking__hall').order_by('-payout_date')

        total_gross = payouts.aggregate(Sum('gross_amount'))['gross_amount__sum'] or Decimal('0.00')
        total_commission = payouts.aggregate(Sum('commission_amount'))['commission_amount__sum'] or Decimal('0.00')
        total_net = payouts.aggregate(Sum('net_amount'))['net_amount__sum'] or Decimal('0.00')

        total_paid = payouts.filter(status=PayoutStatus.PAID).aggregate(Sum('net_amount'))['net_amount__sum'] or Decimal('0.00')
        total_pending = payouts.filter(status__in=[PayoutStatus.SCHEDULED, PayoutStatus.PROCESSING]).aggregate(Sum('net_amount'))['net_amount__sum'] or Decimal('0.00')

        next_payout = payouts.filter(status__in=[PayoutStatus.SCHEDULED, PayoutStatus.PROCESSING]).order_by('payout_date').first()

        breakdown_items = []
        for p in payouts:
            breakdown_items.append({
                "id": str(p.id),
                "booking_id": str(p.booking.id),
                "booking_number": p.booking.booking_number,
                "hall_name": p.booking.hall.name,
                "event_date": p.booking.event_date.isoformat(),
                "gross_amount": float(p.gross_amount),
                "commission_rate": float(p.commission_rate),
                "commission_amount": float(p.commission_amount),
                "net_amount": float(p.net_amount),
                "status": p.status,
                "payout_date": p.payout_date.isoformat(),
                "transaction_reference": p.transaction_reference,
            })

        owner_profile = getattr(owner, 'owner_profile', None)

        return {
            "summary": {
                "total_gross": float(total_gross),
                "total_commission": float(total_commission),
                "commission_rate_pct": float(cls.get_platform_commission_rate()),
                "total_net": float(total_net),
                "total_paid": float(total_paid),
                "total_pending": float(total_pending),
                "next_payout_amount": float(next_payout.net_amount) if next_payout else 0.0,
                "next_payout_date": next_payout.payout_date.isoformat() if next_payout else None,
            },
            "bank_account": {
                "holder_name": owner_profile.bank_account_holder if owner_profile else "",
                "masked_account": owner_profile.masked_account_number if owner_profile else "****",
                "ifsc_code": owner_profile.bank_ifsc_code if owner_profile else "",
                "payout_enabled": owner_profile.payout_enabled if owner_profile else False,
            },
            "payouts": breakdown_items
        }
