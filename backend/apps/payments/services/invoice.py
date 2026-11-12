from datetime import datetime
from decimal import Decimal
from apps.bookings.models import Booking

class InvoiceService:
    @staticmethod
    def generate_invoice_data(booking: Booking) -> dict:
        """
        Builds a compliant Indian GST Tax Invoice data dictionary for a booking.
        """
        hall = booking.hall
        owner = hall.owner
        owner_profile = getattr(owner, 'owner_profile', None)

        invoice_number = f"INV-{booking.event_date.year}-{str(booking.id)[:8].upper()}"
        
        # Line Items
        items = [
            {
                "description": f"Function Hall Base Rent ({booking.time_slot} Slot)",
                "sac_code": "997212",
                "rate": float(booking.hall_rent),
                "quantity": 1,
                "amount": float(booking.hall_rent),
            }
        ]

        if booking.has_catering and booking.catering_amount > 0:
            items.append({
                "description": f"In-house Catering ({booking.guest_count} Guests @ ₹{booking.catering_plate_price}/plate)",
                "sac_code": "996331",
                "rate": float(booking.catering_plate_price),
                "quantity": booking.guest_count,
                "amount": float(booking.catering_amount),
            })

        if booking.has_decor and booking.decor_amount > 0:
            items.append({
                "description": "Stage & Ambient Floral Decor",
                "sac_code": "998399",
                "rate": float(booking.decor_amount),
                "quantity": 1,
                "amount": float(booking.decor_amount),
            })

        if booking.has_dj and booking.dj_amount > 0:
            items.append({
                "description": "DJ Sound System & Acoustic Lighting",
                "sac_code": "999612",
                "rate": float(booking.dj_amount),
                "quantity": 1,
                "amount": float(booking.dj_amount),
            })

        subtotal = float(booking.subtotal)
        cgst_amount = round(subtotal * 0.09, 2)
        sgst_amount = round(subtotal * 0.09, 2)
        tax_total = cgst_amount + sgst_amount
        total = float(booking.total_amount)
        paid = float(booking.amount_paid)
        balance = round(total - paid, 2)

        return {
            "invoice_number": invoice_number,
            "invoice_date": datetime.now().strftime("%Y-%m-%d"),
            "booking_number": booking.booking_number,
            "status": booking.status,
            "seller": {
                "business_name": owner_profile.business_name if owner_profile else hall.name,
                "gstin": owner_profile.pan_gst_number if owner_profile and owner_profile.pan_gst_number else "36AABCG1234F1Z5",
                "address": f"{hall.address_line1}, {hall.locality}, {hall.city} - {hall.postal_code}",
                "contact_email": owner.email,
                "contact_phone": owner.phone or "",
            },
            "customer": {
                "full_name": booking.contact_name or booking.customer.full_name,
                "email": booking.customer.email,
                "phone": booking.contact_phone or booking.customer.phone or "",
            },
            "event_details": {
                "venue_name": hall.name,
                "event_type": booking.event_type,
                "event_date": booking.event_date.isoformat(),
                "time_slot": booking.time_slot,
                "guest_count": booking.guest_count,
            },
            "items": items,
            "financial_summary": {
                "subtotal": subtotal,
                "discount": float(booking.discount_amount),
                "cgst_rate_pct": 9.0,
                "cgst_amount": cgst_amount,
                "sgst_rate_pct": 9.0,
                "sgst_amount": sgst_amount,
                "total_tax": tax_total,
                "grand_total": total,
                "amount_paid": paid,
                "balance_due": balance,
            },
            "payment_history": [
                {
                    "reference": p.payment_reference,
                    "method": p.payment_method,
                    "amount": float(p.amount),
                    "status": p.status,
                    "paid_at": p.paid_at.isoformat() if p.paid_at else None,
                }
                for p in booking.payments.filter(status='SUCCESS')
            ]
        }
