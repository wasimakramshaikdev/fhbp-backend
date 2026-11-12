# Database Schema & Entity Relationship Diagram (ERD)

## 1. Database Principles & Storage Engine

The HallBook database is built on **PostgreSQL 16** with strict enforcement of ACID transactions, foreign-key relational integrity, check constraints, composite unique constraints, and optimized indexes.

- **Monetary Types**: All currency fields utilize `DECIMAL(12, 2)` (never floating point).
- **Primary Keys**: UUIDv4 (`UUIDField(primary_key=True, default=uuid.uuid4, editable=False)`) for public-facing resources to eliminate enumeration attacks (IDOR), and sequential integers for internal audit logs.
- **Audit Columns**: Abstract `TimeStampedModel` provides `created_at` and `updated_at` timestamps on all models.

---

## 2. Comprehensive Entity Relationship Diagram

```
 +----------------------------------------------------------------------------------------------------+
 |                                          USERS & ACCOUNTS                                          |
 +----------------------------------------------------------------------------------------------------+
 | User                                  1 ─── 1  OwnerProfile                                        |
 | - id: UUID (PK)                                - id: UUID (PK)                                     |
 | - email: VARCHAR(255) (UNIQUE)                 - user_id: UUID (FK -> User, UNIQUE)                |
 | - phone: VARCHAR(20) (UNIQUE)                  - business_name: VARCHAR(255)                       |
 | - full_name: VARCHAR(150)                      - registration_number: VARCHAR(100)                 |
 | - role: VARCHAR(20) [CUSTOMER, OWNER, ADMIN]   - pan_gst_number: VARCHAR(50)                       |
 | - is_active: BOOLEAN                           - bank_account_holder: VARCHAR(150)                 |
 | - is_verified: BOOLEAN                         - bank_account_number: VARCHAR(50) (Masked/Encrypted|
 | - created_at: TIMESTAMPTZ                      - bank_ifsc_code: VARCHAR(20)                       |
 | - updated_at: TIMESTAMPTZ                      - verification_status: VARCHAR(20)                  |
 +-----------------------------------+            - payout_enabled: BOOLEAN                           |
                                     |            +---------------------------------------------------+
                                     |                                      │
                                     |                                      │ 1
                                     |                                      │
                                     |                                      ▼ N
 +-----------------------------------+----------------------------------------------------------------+
 |                                                HALLS DOMAIN                                        |
 +----------------------------------------------------------------------------------------------------+
 | Hall                                  1 ─── N  HallImage                                           |
 | - id: UUID (PK)                                - id: UUID (PK)                                     |
 | - owner_id: UUID (FK -> User)                  - hall_id: UUID (FK -> Hall)                        |
 | - name: VARCHAR(255)                           - image: VARCHAR(500) (URL/S3 Key)                  |
 | - slug: VARCHAR(255) (UNIQUE)                  - sort_order: INTEGER                               |
 | - description: TEXT                            - is_primary: BOOLEAN                               |
 | - address_line1: VARCHAR(255)                  - alt_text: VARCHAR(255)                            |
 | - city: VARCHAR(100) (Indexed)                 +---------------------------------------------------+
 | - locality: VARCHAR(100) (Indexed)                                                                 |
 | - postal_code: VARCHAR(20)                     N ─── N  Amenity (via HallAmenity)                  |
 | - latitude: DECIMAL(9, 6)                               - id: UUID (PK)                            |
 | - longitude: DECIMAL(9, 6)                              - name: VARCHAR(100) (UNIQUE)               |
 | - min_capacity: INTEGER                                 - slug: VARCHAR(100) (UNIQUE)               |
 | - max_capacity: INTEGER                                 - icon: VARCHAR(50)                        |
 | - hall_type: VARCHAR(30) [AC, NON_AC, LAWN, HYBRID]     - is_active: BOOLEAN                       |
 | - base_price_morning: DECIMAL(12, 2)                    +------------------------------------------+
 | - base_price_evening: DECIMAL(12, 2)                                                               |
 | - base_price_full_day: DECIMAL(12, 2)                                                              |
 | - advance_percentage: DECIMAL(5, 2) (Default 20.00%)                                               |
 | - catering_policy: VARCHAR(30) [IN_HOUSE_ONLY, OUTSIDE_ALLOWED, BOTH]                              |
 | - veg_plate_price: DECIMAL(10, 2)                                                                  |
 | - non_veg_plate_price: DECIMAL(10, 2)                                                              |
 | - decor_price: DECIMAL(10, 2)                                                                      |
 | - dj_price: DECIMAL(10, 2)                                                                         |
 | - cancellation_policy: VARCHAR(30) [FLEXIBLE, MODERATE, STRICT]                                    |
 | - status: VARCHAR(20) [ACTIVE, INACTIVE]                                                           |
 | - approval_status: VARCHAR(20) [DRAFT, UNDER_REVIEW, APPROVED, REJECTED, SUSPENDED, DEACTIVATED]     |
 | - rejection_reason: TEXT                                                                           |
 +-----------------------------------+----------------------------------------------------------------+
                                     │ 1
                                     ├────────────────────────────────────────┐
                                     │                                        │
                                     ▼ N                                      ▼ N
 +-----------------------------------+------+   +-----------------------------+-----------------------+
 | HallSlotAvailability                     |   | Booking                                             |
 +------------------------------------------+   +-----------------------------------------------------+
 | - id: UUID (PK)                          |   | - id: UUID (PK)                                     |
 | - hall_id: UUID (FK -> Hall)             |   | - booking_number: VARCHAR(30) (UNIQUE)              |
 | - date: DATE                             |   | - customer_id: UUID (FK -> User)                    |
 | - slot: VARCHAR(20) [MORNING, EVENING,   |   | - hall_id: UUID (FK -> Hall)                        |
 |                     FULL_DAY]            |   | - event_type: VARCHAR(50)                           |
 | - status: VARCHAR(20) [OPEN, BOOKED,     |   | - event_date: DATE                                  |
 |                       BLOCKED, HELD]     |   | - time_slot: VARCHAR(20)                            |
 | - booking_id: UUID (FK -> Booking, Null) |   | - guest_count: INTEGER                              |
 | - held_until: TIMESTAMPTZ (Null)         |   | - has_catering: BOOLEAN                             |
 | - blocked_reason: VARCHAR(255)           |   | - catering_plate_type: VARCHAR(20)                  |
 | - lock_version: INTEGER (Optimistic lock)|   | - catering_plate_price: DECIMAL(10, 2)              |
 | UNIQUE (hall_id, date, slot)             |   | - has_decor: BOOLEAN                                |
 +------------------------------------------+   | - has_dj: BOOLEAN                                   |
                                                | - hall_rent: DECIMAL(12, 2)                         |
                                                | - catering_amount: DECIMAL(12, 2)                   |
                                                | - decor_amount: DECIMAL(12, 2)                      |
                                                | - dj_amount: DECIMAL(12, 2)                         |
                                                | - subtotal: DECIMAL(12, 2)                          |
                                                | - discount_amount: DECIMAL(12, 2)                   |
                                                | - tax_rate: DECIMAL(5, 2)                           |
                                                | - tax_amount: DECIMAL(12, 2)                        |
                                                | - total_amount: DECIMAL(12, 2)                      |
                                                | - advance_percentage: DECIMAL(5, 2)                 |
                                                | - advance_amount: DECIMAL(12, 2)                    |
                                                | - balance_amount: DECIMAL(12, 2)                    |
                                                | - amount_paid: DECIMAL(12, 2)                       |
                                                | - status: VARCHAR(30) [PAYMENT_PENDING,             |
                                                |            PENDING_OWNER_CONFIRMATION, CONFIRMED,   |
                                                |            REJECTED, CANCELLED_BY_CUSTOMER,         |
                                                |            CANCELLED_BY_OWNER, COMPLETED, DISPUTED, |
                                                |            REFUND_PENDING, REFUNDED]                |
                                                | - owner_response_notes: TEXT                        |
                                                | - cancellation_reason: TEXT                         |
                                                | - cancellation_fee: DECIMAL(12, 2)                  |
                                                | - refund_amount: DECIMAL(12, 2)                     |
                                                | - expires_at: TIMESTAMPTZ                           |
                                                +--------------------------+--------------------------+
                                                                           │
                                           ┌───────────────────────────────┼──────────────────────────────┐
                                           │ 1                             │ 1                            │ 1
                                           ▼ N                             ▼ 1                            ▼ 1
 +-----------------------------------------+----+  +-----------------------+-----+  +---------------------+----+
 | Payment                                      |  | Review                              |  | Dispute                             |
 +----------------------------------------------+  +-------------------------------------+  +-------------------------------------+
 | - id: UUID (PK)                              |  | - id: UUID (PK)                     |  | - id: UUID (PK)                     |
 | - booking_id: UUID (FK -> Booking)           |  | - booking_id: UUID (FK, UNIQUE)     |  | - booking_id: UUID (FK, UNIQUE)     |
 | - payment_reference: VARCHAR(100) (UNIQUE)   |  | - customer_id: UUID (FK -> User)    |  | - opened_by_id: UUID (FK -> User)   |
 | - idempotency_key: VARCHAR(255) (UNIQUE)     |  | - hall_id: UUID (FK -> Hall)        |  | - reason: VARCHAR(100)              |
 | - amount: DECIMAL(12, 2)                     |  | - rating: SMALLINT (1..5)           |  | - description: TEXT                 |
 | - currency: VARCHAR(3) (Default 'INR')       |  | - comment: TEXT                     |  | - evidence_urls: JSONB              |
 | - payment_type: VARCHAR(20) [ADVANCE, BALANCE|  | - owner_response: TEXT              |  | - status: VARCHAR(30) [OPEN,        |
 |                             FULL, REFUND]    |  | - owner_responded_at: TIMESTAMPTZ   |  |    UNDER_REVIEW, RESOLVED, CLOSED]  |
 | - payment_method: VARCHAR(30) [UPI, CARD, NB]|  | - is_published: BOOLEAN             |  | - resolution_type: VARCHAR(30)      |
 | - status: VARCHAR(20) [INITIATED, PENDING,   |  | - created_at: TIMESTAMPTZ           |  | - refund_amount: DECIMAL(12, 2)     |
 |                       SUCCESS, FAILED]       |  +-------------------------------------+  | - admin_notes: TEXT                 |
 | - gateway: VARCHAR(30) [RAZORPAY, STRIPE]    |                                           | - resolved_by_id: UUID (FK -> User) |
 | - gateway_order_id: VARCHAR(255)             |                                           | - resolved_at: TIMESTAMPTZ          |
 | - gateway_payment_id: VARCHAR(255)           |                                           +-------------------------------------+
 | - gateway_signature: VARCHAR(500)            |
 | - gateway_response_payload: JSONB            |
 | - paid_at: TIMESTAMPTZ                       |
 +-----------------------+----------------------+
                         │ 1
                         ▼ N
 +-----------------------+----------------------+  +-------------------------------------+  +-------------------------------------+
 | Refund                                       |  | Payout                              |  | Favorite                            |
 +----------------------------------------------+  +-------------------------------------+  +-------------------------------------+
 | - id: UUID (PK)                              |  | - id: UUID (PK)                     |  | - id: UUID (PK)                     |
 | - payment_id: UUID (FK -> Payment)           |  | - owner_id: UUID (FK -> User)       |  | - customer_id: UUID (FK -> User)    |
 | - booking_id: UUID (FK -> Booking)           |  | - booking_id: UUID (FK -> Booking)  |  | - hall_id: UUID (FK -> Hall)        |
 | - refund_reference: VARCHAR(100) (UNIQUE)    |  | - gross_amount: DECIMAL(12, 2)      |  | - created_at: TIMESTAMPTZ           |
 | - amount: DECIMAL(12, 2)                     |  | - commission_rate: DECIMAL(5, 2)    |  | UNIQUE (customer_id, hall_id)       |
 | - currency: VARCHAR(3) (Default 'INR')       |  | - commission_amount: DECIMAL(12, 2) |  +-------------------------------------+
 | - reason: TEXT                               |  | - net_amount: DECIMAL(12, 2)        |
 | - status: VARCHAR(20) [PENDING, SUCCESS,     |  | - status: VARCHAR(20) [SCHEDULED,   |  +-------------------------------------+
 |                        FAILED]               |  |     PROCESSING, PAID, FAILED, HOLD] |  | Notification                        |
 | - initiated_by_id: UUID (FK -> User)         |  | - payout_date: DATE                 |  +-------------------------------------+
 | - gateway_refund_id: VARCHAR(255)            |  | - transaction_ref: VARCHAR(100)     |  | - id: UUID (PK)                     |
 | - created_at: TIMESTAMPTZ                    |  | - failure_reason: TEXT              |  | - user_id: UUID (FK -> User)        |
 +----------------------------------------------+  +-------------------------------------+  | - title: VARCHAR(255)               |
                                                                                            | - message: TEXT                     |
 +----------------------------------------------+  +-------------------------------------+  | - type: VARCHAR(50)                 |
 | PlatformSetting                              |  | AuditLog                            |  | - is_read: BOOLEAN (Default False)  |
 +----------------------------------------------+  +-------------------------------------+  | - related_entity_type: VARCHAR(50)  |
 | - id: UUID (PK)                              |  | - id: BIGSERIAL (PK)                |  | - related_entity_id: UUID           |
 | - key: VARCHAR(100) (UNIQUE)                 |  | - actor_id: UUID (FK -> User, Null) |  | - created_at: TIMESTAMPTZ           |
 | - value: JSONB                               |  | - action: VARCHAR(100)              |  +-------------------------------------+
 | - description: TEXT                          |  | - object_type: VARCHAR(100)         |
 | - updated_by_id: UUID (FK -> User)           |  | - object_id: VARCHAR(100)           |
 | - updated_at: TIMESTAMPTZ                    |  | - ip_address: INET                  |
 +----------------------------------------------+  | - user_agent: VARCHAR(500)          |
                                                   | - changes: JSONB                    |
                                                   | - created_at: TIMESTAMPTZ           |
                                                   +-------------------------------------+
```

---

## 3. Critical Constraints & Indexes

1. **Check Constraints**:
   - `chk_hall_capacity`: `min_capacity > 0 AND max_capacity >= min_capacity`
   - `chk_booking_guests`: `guest_count > 0`
   - `chk_review_rating`: `rating >= 1 AND rating <= 5`
   - `chk_advance_pct`: `advance_percentage >= 0.00 AND advance_percentage <= 100.00`
   - `chk_positive_amounts`: `total_amount >= 0 AND advance_amount >= 0 AND balance_amount >= 0`

2. **Compound Unique Constraints**:
   - `unique_hall_slot`: `(hall_id, date, slot)` on `HallSlotAvailability`
   - `unique_customer_favorite`: `(customer_id, hall_id)` on `Favorite`
   - `unique_booking_review`: `(booking_id)` on `Review` (One review per completed booking)
   - `unique_idempotency_key`: `(idempotency_key)` on `Payment`

3. **Performance Indexes**:
   - `idx_halls_search`: `(city, locality, approval_status, status)`
   - `idx_halls_capacity_price`: `(min_capacity, max_capacity, base_price_morning)`
   - `idx_availability_query`: `(hall_id, date, status)`
   - `idx_bookings_customer`: `(customer_id, status, created_at DESC)`
   - `idx_bookings_owner_date`: `(hall_id, event_date, status)`
   - `idx_notifications_unread`: `(user_id, is_read, created_at DESC)`
