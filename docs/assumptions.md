# Project Assumptions & Domain Rules

## 1. Geographical & Market Scope
- **Initial Territory**: Metropolitan Hyderabad, Telangana, India (Localities: Madhapur, Gachibowli, Kondapur, Banjara Hills, Jubilee Hills, Hitech City, Kukatpally).
- **Currency & Taxation**: Standard currency is Indian Rupee (`INR` / `₹`). Default goods and services tax (GST) is configured at 18% (9% CGST + 9% SGST), customizable via Admin Platform Settings.

---

## 2. Hall Booking & Availability Model
- **Slot Boundaries**:
  - `MORNING`: 08:00 AM – 02:00 PM (6 hours)
  - `EVENING`: 04:00 PM – 11:00 PM (7 hours)
  - `FULL_DAY`: 08:00 AM – 11:00 PM (15 hours)
- **Mutual Exclusivity**: A Full Day booking blocks both Morning and Evening slots for that calendar day.
- **Hold Window**: When a customer initiates payment, a temporary reservation (`HELD`) locks the slot for exactly **15 minutes**. If payment is not completed within 15 minutes, Celery Beat releases the slot back to `OPEN`.

---

## 3. Financial & Commission Rules
- **Advance Deposit**: Default advance is 20% of total booking value, payable online during checkout.
- **Balance Payment**: Remaining 80% is payable through the Customer Dashboard prior to the event date.
- **Platform Commission**: Default platform fee is **10% of gross booking amount**, deducted prior to owner payout.
- **Payout Settlement Buffer**: Owner payouts are scheduled for dispatch $T+3$ days following event completion, provided no active dispute is lodged.

---

## 4. Cancellation & Dispute Rules
- **Cancellation Policy Tiers**:
  - *Flexible*: Full refund (minus 5% gateway fee) up to 14 days before event; 50% refund up to 7 days before.
  - *Moderate*: 70% refund up to 30 days before; 30% refund up to 14 days before.
  - *Strict*: 50% refund up to 30 days before; 0% refund thereafter.
- **Dispute Settlement**: Super Admin holds sole authority to issue discretionary refunds or release funds to the hall owner.
