# System Architecture — HallBook Platform

## 1. Executive Summary & Topology

**HallBook** is a production-grade Function Hall Booking Marketplace connecting customers searching for event venues (weddings, corporate events, birthdays, engagements, receptions) with hall owners, overseen by platform administrators.

The architecture is implemented as a **Modular Monolith** optimized for reliability, transaction safety, data integrity, and strict concurrency control:

```
┌────────────────────────────────────────────────────────┐
│                   React 18 + Tailwind CSS               │
│            (Feature-Based Architecture + Vite)         │
└───────────────────────────┬────────────────────────────┘
                            │ HTTPS (REST API / JSON)
┌───────────────────────────▼────────────────────────────┐
│                  Nginx Reverse Proxy                   │
│   (SSL Termination, Rate Limiting, Static Caching)     │
└───────────────────────────┬────────────────────────────┘
                            │ WSGI (Gunicorn)
┌───────────────────────────▼────────────────────────────┐
│             Django 5.0 + Django REST Framework        │
│    ┌──────────────────────────────────────────────┐    │
│    │               Core Service Layer             │    │
│    │  - PricingService     - BookingStateMachine  │    │
│    │  - AvailabilityService - PaymentGatewayAdapter│    │
│    │  - PayoutService      - AuditLoggerService   │    │
│    └──────────────────────────────────────────────┘    │
└──────────────┬──────────────────────────┬──────────────┘
               │                          │
┌──────────────▼─────────────┐   ┌────────▼─────────────┐
│    PostgreSQL 16 Database  │   │     Redis 7 Cache    │
│  - Authoritative Data Store│   │ - Broker for Celery  │
│  - ACID Transactions       │   │ - Ephemeral Locks    │
│  - Row-Level Locking       │   │ - Query Result Cache │
│  - Constraints & Indexes   │   │ - Rate Limit Counters│
└────────────────────────────┘   └────────┬─────────────┘
                                          │
                                 ┌────────▼─────────────┐
                                 │    Celery Workers    │
                                 │ - Async Notifications│
                                 │ - Email Dispatch     │
                                 │ - Invoice Generation │
                                 │ - Image Optimization │
                                 └────────┬─────────────┘
                                          │
                                 ┌────────▼─────────────┐
                                 │     Celery Beat      │
                                 │ - Booking Expiration │
                                 │ - Balance Reminders  │
                                 │ - Payout Sweeper     │
                                 └──────────────────────┘
```

---

## 2. Component & Modular Service Architecture

To prevent a monolithic codebase from degenerating into tight coupling, the backend is partitioned into distinct, domain-driven Django applications:

```
backend/
├── config/                  # Django project configuration, wsgi, asgi, celery app, settings
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   ├── test.py
│   │   └── production.py
│   ├── urls.py
│   └── celery.py
├── apps/
│   ├── core/                # Base models (Timestamped, UUID), standard responses, audit logs
│   ├── accounts/            # Custom User model, OwnerProfile, JWT tokens, RBAC permissions
│   ├── halls/               # Hall, HallImage, Amenity, Pricing rules, Owner listings
│   ├── availability/        # Slots, Calendar engine, Block/Unblock, Concurrency locks
│   ├── bookings/            # Booking state machine, Pricing calculation service, Holds
│   ├── payments/            # Gateway abstraction, Razorpay/Stripe, Webhooks, Invoicing, Refunds
│   ├── reviews/             # Ratings, Customer reviews, Owner responses
│   ├── favorites/           # Customer saved halls
│   ├── notifications/       # Multi-channel notifications (In-app, Email queues)
│   ├── disputes/            # Dispute lifecycle, Evidence handling, Admin resolution
│   ├── payouts/             # Owner payout calculation, Commission deductions, Settlements
│   └── dashboard/           # Metrics aggregation for Customer, Owner, and Super Admin
```

---

## 3. Service Layer Specifications

Business-critical operations are strictly encapsulated within a dedicated Python service layer rather than distributed across views or serializers:

1. **`PricingService`** (`apps/bookings/services/pricing.py`):
   - Computes:
     $$\text{Hall Rent} = \text{Base Price for Slot (Morning / Evening / Full Day)}$$
     $$\text{Catering Amount} = \text{Guest Count} \times \text{Per-Plate Price (if selected)}$$
     $$\text{Addon Amounts} = \text{Decor Price} + \text{DJ Price}$$
     $$\text{Subtotal} = \text{Hall Rent} + \text{Catering Amount} + \text{Decor Amount} + \text{DJ Amount}$$
     $$\text{Discount Amount} = \text{Subtotal} \times \text{Discount Percentage}$$
     $$\text{Tax Amount} = (\text{Subtotal} - \text{Discount Amount}) \times \text{Tax Rate (e.g., 18\% GST)}$$
     $$\text{Total Amount} = \text{Subtotal} - \text{Discount Amount} + \text{Tax Amount}$$
     $$\text{Advance Amount} = \text{Total Amount} \times \text{Advance Percentage (e.g., 20\%)}$$
     $$\text{Balance Amount} = \text{Total Amount} - \text{Advance Amount}$$
   - Freezes calculated financial values onto the `Booking` record to guarantee historical accuracy.

2. **`AvailabilityService`** (`apps/availability/services/availability.py`):
   - Evaluates slot compatibility (Morning: 08:00–14:00, Evening: 16:00–23:00, Full Day: 08:00–23:00).
   - Manages slot mutual exclusivity (booking "Full Day" blocks both "Morning" and "Evening"; booking "Morning" blocks "Full Day").
   - Implements PostgreSQL `select_for_update` row locks during booking checkout to eliminate double bookings.

3. **`BookingStateMachine`** (`apps/bookings/services/state_machine.py`):
   - Enforces validated transitions across booking lifecycle states.
   - Prevents illegal status jumps (e.g. bypassing payment or directly modifying confirmed records).

4. **`PaymentGatewayAdapter`** (`apps/payments/services/gateway.py`):
   - Abstract base class interface defining `create_order`, `verify_signature`, `fetch_payment_status`, and `initiate_refund`.
   - Implementations for `RazorpayGateway`, `StripeGateway`, and `SimulatedGateway` (for deterministic automated test suites).

5. **`PayoutService`** (`apps/payouts/services/payout.py`):
   - Calculates platform commission ($Gross \times Platform\%$) and net owner payouts.
   - Applies dispute holds and settlement delay buffers (e.g. $T+3$ days post-event completion).

6. **`AuditLoggerService`** (`apps/core/services/audit.py`):
   - Captures administrative and high-value financial actions with actor ID, target entity, timestamp, IP address, and payload delta.

---

## 4. Frontend Architecture

The frontend is structured in React 18 using a clean feature-based modular layout:

```
frontend/src/
├── app/                     # App configuration, providers (Auth, Toast, Notification, QueryClient)
├── assets/                  # Static assets, SVG icons, brand graphics
├── components/              # Shared UI Design System components (Button, Modal, Input, Badge, Table, etc.)
├── layouts/                 # Layout wrappers (PublicLayout, CustomerLayout, OwnerLayout, AdminLayout)
├── features/                # Domain-driven feature slices
│   ├── auth/                # Login, Register, Password Reset, Verification components & hooks
│   ├── search/              # Search bar, Filter sidebar, Map view, Result cards
│   ├── halls/               # Hall detail view, Gallery, Amenities grid, Pricing card
│   ├── availability/        # Interactive booking calendar, Slot picker
│   ├── bookings/            # Multi-step checkout (Details -> Payment -> Confirmation), My Bookings
│   ├── payments/            # Payment gateway checkout modal, Invoice downloader
│   ├── reviews/             # Review submission modal, Rating summary, Owner response editor
│   ├── favorites/           # Saved halls grid and toggle controls
│   ├── owner/               # Owner onboarding wizard, Calendar manager, Booking requests, Earnings
│   └── admin/               # Approvals queue, Dispute resolver, Owner management, Platform settings
├── services/                # Axios API client instances with interceptors and token refresh
├── routes/                  # React Router 6 configuration with RoleProtectedRoute guards
├── hooks/                   # Custom hooks (useAuth, useDebounce, useAvailability, usePagination)
└── utils/                  # Formatters (currency INR, date, phone), validators, constants
```
