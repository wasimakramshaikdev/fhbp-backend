# REST API Specification — HallBook Platform

All API endpoints are versioned under `/api/v1/`.

## 1. Standard Response & Error Envelope Format

### Standard Success Response
```json
{
  "success": true,
  "data": {},
  "message": "Operation completed successfully.",
  "meta": {
    "page": 1,
    "page_size": 20,
    "total_count": 142,
    "total_pages": 8
  }
}
```

### Standard Error Response
```json
{
  "success": false,
  "message": "Validation failed on the submitted booking parameters.",
  "errors": {
    "guest_count": ["Guest count (600) exceeds maximum capacity (500) for this hall."],
    "time_slot": ["Selected time slot 'EVENING' is already reserved on 2026-08-12."]
  },
  "code": "VALIDATION_ERROR"
}
```

---

## 2. Comprehensive Endpoint Matrix

### 2.1 Authentication & User Profile (`/api/v1/auth/`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/api/v1/auth/register/` | Public | Register as Customer or Hall Owner |
| `POST` | `/api/v1/auth/login/` | Public | Authenticate with email/password; returns JWT + HttpOnly Cookie |
| `POST` | `/api/v1/auth/refresh/` | Public (Cookie) | Rotate Refresh Token and return new Access Token |
| `POST` | `/api/v1/auth/logout/` | Authenticated | Invalidate refresh token and clear cookies |
| `GET` | `/api/v1/auth/me/` | Authenticated | Retrieve current user profile & role permissions |
| `PATCH`| `/api/v1/auth/me/` | Authenticated | Update user name, phone, or profile attributes |
| `POST` | `/api/v1/auth/password-reset/` | Public | Initiate password reset email with secure token |
| `POST` | `/api/v1/auth/password-reset/confirm/` | Public | Reset password with token and new password |

### 2.2 Halls & Search Catalog (`/api/v1/halls/`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/api/v1/halls/` | Public | Filtered & paginated search (`city`, `locality`, `date`, `guests`, `capacity_min`, `capacity_max`, `price_min`, `price_max`, `hall_type`, `amenities`, `sort`, `page`) |
| `GET` | `/api/v1/halls/featured/` | Public | Featured halls for homepage banner (cached in Redis) |
| `GET` | `/api/v1/halls/amenities/` | Public | List all active hall amenities |
| `GET` | `/api/v1/halls/{id_or_slug}/` | Public | Detailed hall profile with images, amenities, pricing, reviews |
| `POST` | `/api/v1/halls/` | Owner | Create draft hall listing (Owner Onboarding Step 1) |
| `PATCH`| `/api/v1/halls/{id}/` | Owner / Admin | Update listing details or pricing rules |
| `POST` | `/api/v1/halls/{id}/images/` | Owner | Upload hall imagery (multi-part form upload with MIME validation) |
| `DELETE`| `/api/v1/halls/{id}/images/{img_id}/` | Owner | Delete image from gallery |
| `POST` | `/api/v1/halls/{id}/submit/` | Owner | Submit draft hall for Super Admin approval |
| `POST` | `/api/v1/halls/{id}/toggle-status/` | Owner | Activate or deactivate live hall listing |

### 2.3 Calendar & Availability (`/api/v1/availability/`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/api/v1/halls/{id}/availability/` | Public | Fetch month availability matrix (`year`, `month` query params) |
| `POST` | `/api/v1/halls/{id}/availability/check/` | Public | Real-time pricing check for date, slot, guests, and addons |
| `POST` | `/api/v1/halls/{id}/availability/block/` | Owner | Owner manually blocks date/slot |
| `POST` | `/api/v1/halls/{id}/availability/unblock/`| Owner | Owner unblocks previously blocked slot |

### 2.4 Bookings & Checkout (`/api/v1/bookings/`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/api/v1/bookings/create-intent/` | Customer | Concurrency-locked booking intent with price freeze & slot hold |
| `GET` | `/api/v1/bookings/` | Customer | List current customer's booking history |
| `GET` | `/api/v1/bookings/{id}/` | Customer / Owner / Admin | Retrieve full booking breakdown with breakdown items |
| `POST` | `/api/v1/bookings/{id}/cancel/` | Customer / Owner | Cancel booking based on policy tier |
| `POST` | `/api/v1/bookings/{id}/accept/` | Owner | Owner accepts pending booking request |
| `POST` | `/api/v1/bookings/{id}/reject/` | Owner | Owner rejects booking request (triggers automated refund) |

### 2.5 Payments & Webhooks (`/api/v1/payments/`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/api/v1/payments/initiate/` | Customer | Create Gateway Order for advance or balance payment |
| `POST` | `/api/v1/payments/verify/` | Customer | Verify gateway signature and confirm payment server-side |
| `POST` | `/api/v1/payments/webhook/` | Public (Signature) | Webhook callback from Razorpay / Stripe for idempotent payment state sync |
| `GET` | `/api/v1/payments/{id}/invoice/` | Customer / Owner | Download PDF / JSON formatted tax invoice |

### 2.6 Reviews & Favorites (`/api/v1/reviews/`, `/api/v1/favorites/`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/api/v1/halls/{id}/reviews/` | Public | Paginated reviews for a hall |
| `POST` | `/api/v1/bookings/{id}/review/` | Customer | Leave 1–5 star review on completed booking |
| `POST` | `/api/v1/reviews/{id}/respond/` | Owner | Hall owner public response to a customer review |
| `GET` | `/api/v1/favorites/` | Customer | List all saved halls for logged-in user |
| `POST` | `/api/v1/favorites/{hall_id}/toggle/` | Customer | Add or remove hall from favorites |

### 2.7 Owner Dashboard & Operations (`/api/v1/owner/`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/api/v1/owner/dashboard/` | Owner | Aggregated stats: pending requests, monthly revenue, rating |
| `GET` | `/api/v1/owner/bookings/` | Owner | Filterable list of booking requests |
| `GET` | `/api/v1/owner/calendar/` | Owner | Month calendar view with booked/blocked status |
| `GET` | `/api/v1/owner/listings/` | Owner | List of all properties owned by user |
| `GET` | `/api/v1/owner/earnings/` | Owner | Financial breakdown: gross revenue, 10% commission, net payouts |
| `PATCH`| `/api/v1/owner/payout-settings/` | Owner | Securely update bank account details for payout processing |

### 2.8 Super Admin Control Plane (`/api/v1/admin/`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/api/v1/admin/dashboard/` | Admin | High-level metrics: total halls, active owners, MTD revenue, pending approvals |
| `GET` | `/api/v1/admin/owners/` | Admin | List hall owners with filter by status (`UNDER_REVIEW`, `ACTIVE`, `SUSPENDED`) |
| `POST` | `/api/v1/admin/owners/{id}/action/`| Admin | Approve, reject, or suspend owner account |
| `GET` | `/api/v1/admin/halls/` | Admin | List all listings with approval status filters |
| `POST` | `/api/v1/admin/halls/{id}/approve/`| Admin | Approve submitted hall listing |
| `POST` | `/api/v1/admin/halls/{id}/reject/` | Admin | Reject listing with required rejection reason |
| `GET` | `/api/v1/admin/disputes/` | Admin | List all disputed bookings with customer/owner claims |
| `POST` | `/api/v1/admin/disputes/{id}/resolve/`| Admin | Settle dispute (Issue Full/Partial Refund, Owner Favored, No Action) |
| `GET` | `/api/v1/admin/settings/` | Admin | View platform settings (commission %, tax rate, holding TTL) |
| `PATCH`| `/api/v1/admin/settings/` | Admin | Update system configuration with audit logging |
| `GET` | `/api/v1/admin/audit-logs/` | Admin | Filterable audit log trail |
