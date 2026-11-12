# Booking Concurrency & State Machine Lifecycle

## 1. Concurrency Safety & Pessimistic Locking

The core requirement of HallBook is that **two customers can never successfully book or reserve the same hall for an overlapping time slot on the same date**.

Because there is latency between browsing availability and completing checkout, standard read-then-write patterns fail under concurrent traffic. HallBook implements **Pessimistic Database Row Locking (`select_for_update`)** inside an atomic transaction:

```
Customer A (Slot Check & Hold)                   Customer B (Simultaneous Attempt)
           │                                                    │
           ├──────────── Begin DB Transaction ───────────────>  │
           │                                                    │
           ├─ SELECT * FROM HallSlotAvailability                │
           │  WHERE hall_id=X AND date=Y AND slot=Z             │
           │  FOR UPDATE ───────────────────────────────────────┤
           │  (Acquires PostgreSQL Row Lock)                    │
           │                                                    ├─ Attempts SELECT ... FOR UPDATE
           ├─ Check status == OPEN                              │  (BLOCKED: Waits on lock release)
           ├─ Calculate Price (PricingService)                  │  ...
           ├─ Create Booking (Status: PAYMENT_PENDING)          │  ...
           ├─ Update Slot Status: HELD (expires_at: +15m)       │  ...
           ├─ Commit DB Transaction ───────────────────────────>│  ...
           │  (Releases Row Lock)                               │
           │                                                    ├─ Lock acquired! Reads Slot Status
           │                                                    ├─ Status is now HELD (Not OPEN)
           │                                                    ├─ Rollback & Raise HTTP 409 Conflict:
           │                                                    │  "Slot is temporarily reserved."
```

---

## 2. Slot Mutual Exclusivity Rules

A hall can be booked in three standard configurations:
- **`MORNING`** (08:00 – 14:00)
- **`EVENING`** (16:00 – 23:00)
- **`FULL_DAY`** (08:00 – 23:00)

### Conflict Detection Matrix
| Requested Slot | If existing slot is MORNING | If existing slot is EVENING | If existing slot is FULL_DAY |
|---|:---:|:---:|:---:|
| **MORNING** | ❌ Conflict | ✅ Compatible | ❌ Conflict |
| **EVENING** | ✅ Compatible | ❌ Conflict | ❌ Conflict |
| **FULL_DAY** | ❌ Conflict | ❌ Conflict | ❌ Conflict |

When a `FULL_DAY` booking is confirmed, all three slot records (`MORNING`, `EVENING`, `FULL_DAY`) are locked and marked `BOOKED`.

---

## 3. Booking State Machine

```
                    ┌────────────────────────┐
                    │     PAYMENT_PENDING    │
                    │   (15-min Slot Hold)   │
                    └───────────┬────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │ [Payment Success]     │ [Hold Expired / Fail] │ [Customer Cancel]
        ▼                       ▼                       ▼
┌───────────────────────────┐ ┌────────────────────┐ ┌────────────────────┐
│ PENDING_OWNER_CONFIRMATION│ │     EXPIRED        │ │    CANCELLED       │
└───────────┬───────────────┘ └────────────────────┘ └────────────────────┘
            │
    ┌───────┴───────────────┐
    │ [Owner Accepts]       │ [Owner Rejects]
    ▼                       ▼
┌───────────────────┐ ┌────────────────────┐
│    CONFIRMED      │ │    REJECTED        │
└─────────┬─────────┘ │ (Auto Full Refund) │
          │           └────────────────────┘
    ┌─────┴─────────────────┬───────────────────────┐
    │ [Event Date Passes]   │ [Dispute Lodged]      │ [Customer / Owner Cancel]
    ▼                       ▼                       ▼
┌───────────────────┐ ┌────────────────────┐ ┌────────────────────┐
│    COMPLETED      │ │     DISPUTED       │ │    CANCELLED       │
└─────────┬─────────┘ └──────────┬─────────┘ │  (Policy Refund)   │
          │                      │           └────────────────────┘
    ┌─────┴────────┐             │
    │              │             ▼
    ▼              ▼  ┌────────────────────┐
[Customer      [Eligible│  REFUND_PENDING    │
 Review]        for     └──────────┬─────────┘
                Payout]            │ [Admin Settle / Gateway Process]
                                   ▼
                              ┌────────────────────┐
                              │     REFUNDED       │
                              └────────────────────┘
```

---

## 4. State Transitions Table

| Current State | Target State | Triggering Actor | Pre-Conditions & Actions |
|---|---|---|---|
| *(New)* | `PAYMENT_PENDING` | Customer | Slot is `OPEN`; server freezes price; slot marked `HELD` for 15 minutes. |
| `PAYMENT_PENDING` | `EXPIRED` | Celery Beat | Advance payment was not completed within 15 minutes; slot released to `OPEN`. |
| `PAYMENT_PENDING` | `PENDING_OWNER_CONFIRMATION` | System (Webhook) | Advance payment verified; owner notified via email & in-app badge. |
| `PENDING_OWNER_CONFIRMATION`| `CONFIRMED` | Hall Owner | Owner accepts request; slot permanently marked `BOOKED`. |
| `PENDING_OWNER_CONFIRMATION`| `REJECTED` | Hall Owner | Owner declines request; full 100% refund automatically queued via Payment Gateway. |
| `CONFIRMED` | `CANCELLED_BY_CUSTOMER` | Customer | Cancellation fee calculated per hall policy; refund queued; slot released to `OPEN`. |
| `CONFIRMED` | `COMPLETED` | Celery Beat | Event date + slot duration has elapsed; balance was paid; enables customer review. |
| `CONFIRMED` / `COMPLETED` | `DISPUTED` | Customer / Owner | Dispute raised with evidence; freezes owner payout until admin review. |
| `DISPUTED` | `REFUND_PENDING` | Super Admin | Admin rules in favor of customer; queues full or partial refund. |
| `REFUND_PENDING` | `REFUNDED` | System (Webhook) | Gateway confirms refund transaction settlement. |
