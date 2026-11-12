from decimal import Decimal, ROUND_HALF_UP
from apps.halls.models import Hall
from apps.availability.models import TimeSlot

class PricingService:
    @staticmethod
    def quantize(amount: Decimal) -> Decimal:
        """Rounds monetary values to 2 decimal places safely without floating point inaccuracies."""
        return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @classmethod
    def calculate_quote(
        cls,
        hall: Hall,
        slot: str,
        guest_count: int,
        has_catering: bool = False,
        catering_type: str = 'VEG',
        has_decor: bool = False,
        has_dj: bool = False,
        discount_percentage: Decimal = Decimal('0.00')
    ) -> dict:
        """
        Authoritative pricing calculator using Decimal arithmetic.
        """
        if slot == TimeSlot.MORNING:
            hall_rent = Decimal(str(hall.base_price_morning))
        elif slot == TimeSlot.EVENING:
            hall_rent = Decimal(str(hall.base_price_evening))
        else:
            hall_rent = Decimal(str(hall.base_price_full_day))

        per_plate_price = Decimal(str(hall.veg_plate_price)) if catering_type == 'VEG' else Decimal(str(hall.non_veg_plate_price))
        catering_amount = (Decimal(guest_count) * per_plate_price) if has_catering else Decimal('0.00')
        decor_amount = Decimal(str(hall.decor_price)) if has_decor else Decimal('0.00')
        dj_amount = Decimal(str(hall.dj_price)) if has_dj else Decimal('0.00')

        subtotal = hall_rent + catering_amount + decor_amount + dj_amount
        discount_amount = cls.quantize(subtotal * (discount_percentage / Decimal('100.00')))
        taxable_subtotal = subtotal - discount_amount

        tax_rate = Decimal('18.00') # 18% GST (9% CGST + 9% SGST)
        tax_amount = cls.quantize(taxable_subtotal * (tax_rate / Decimal('100.00')))
        total_amount = taxable_subtotal + tax_amount

        advance_pct = Decimal(str(hall.advance_percentage))
        advance_amount = cls.quantize(total_amount * (advance_pct / Decimal('100.00')))
        balance_amount = total_amount - advance_amount

        return {
            "hall_rent": hall_rent,
            "catering_plate_type": catering_type,
            "per_plate_price": per_plate_price,
            "catering_amount": catering_amount,
            "decor_amount": decor_amount,
            "dj_amount": dj_amount,
            "subtotal": subtotal,
            "discount_amount": discount_amount,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "total_amount": total_amount,
            "advance_percentage": advance_pct,
            "advance_amount": advance_amount,
            "balance_amount": balance_amount,
        }
