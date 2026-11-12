# Authentication & Authorization Architecture

## 1. Authentication Strategy

HallBook implements a dual-token JWT architecture paired with secure **HttpOnly, SameSite=Lax** cookies for web browser clients, supplemented by standard `Bearer <token>` support for headless API consumption.

```
Client (Browser)                 Backend (Django DRF)
      │                                    │
      ├───── POST /api/v1/auth/login ─────>│ Validate credentials (Argon2/PBKDF2)
      │      { email, password }           │ Generate Access Token (TTL: 15m)
      │                                    │ Generate Refresh Token (TTL: 7d)
      │<──── Set-Cookie: refresh_token ────┤ Store Refresh Token in DB/Redis blacklist
      │      { access_token, user }        │
      │                                    │
      ├───── Authorization: Bearer <jwt> ─>│ Validate claims & Role permissions
      │                                    │
(Token Expired)                            │
      ├───── POST /api/v1/auth/refresh ───>│ Validate Refresh Cookie
      │<──── Set-Cookie: new_refresh ──────┤ Issue new Access Token (Token Rotation)
      │      { access_token }              │ Invalidate old Refresh Token
```

---

## 2. Role-Based Access Control (RBAC) Matrix

| Resource / Action | Unauthenticated | CUSTOMER | OWNER | SUPER ADMIN |
|---|:---:|:---:|:---:|:---:|
| Search / View Live Halls | ✅ | ✅ | ✅ | ✅ |
| Check Slot Availability & Price | ✅ | ✅ | ✅ | ✅ |
| Add to Favorites | ❌ | ✅ | ❌ | ❌ |
| Create Booking Intent & Pay | ❌ | ✅ | ❌ | ❌ |
| View Own Bookings & Invoices | ❌ | ✅ | ❌ | ✅ (All) |
| Leave Review (Completed Event) | ❌ | ✅ (Self) | ❌ | ❌ |
| Submit New Hall Listing | ❌ | ❌ | ✅ | ✅ |
| Edit Own Hall & Calendar Blocks | ❌ | ❌ | ✅ (Owned) | ✅ (All) |
| Accept / Reject Booking Request | ❌ | ❌ | ✅ (Owned) | ✅ |
| View Owner Payouts & Commission | ❌ | ❌ | ✅ (Owned) | ✅ (All) |
| Respond to Review on Hall | ❌ | ❌ | ✅ (Owned) | ✅ |
| Approve / Reject New Listings | ❌ | ❌ | ❌ | ✅ |
| Suspend / Reactivate Owner | ❌ | ❌ | ❌ | ✅ |
| Resolve Disputes & Issue Refunds | ❌ | ❌ | ❌ | ✅ |
| Modify Platform Commission & Settings| ❌ | ❌ | ❌ | ✅ |
| View Audit Logs | ❌ | ❌ | ❌ | ✅ |

---

## 3. Object-Level Permission Enforcement

To prevent Insecure Direct Object Reference (IDOR) vulnerabilities:

1. **`IsOwnerOrReadOnly`**: Ensures that modifications to halls, images, calendar slots, and payout settings are restricted strictly to the authenticated owner who created the entity.
2. **`IsBookingPartyOrAdmin`**: Restricts booking detail access, payment processing, cancellation requests, and invoice downloads to the booking's `customer`, the venue's `owner`, or a `SUPER_ADMIN`.
3. **`IsReviewAuthor`**: Prevents users from fabricating or modifying reviews for bookings they did not participate in.

```python
# apps/core/permissions.py
from rest_framework import permissions

class IsHallOwner(permissions.BasePermission):
    """Enforces that only the owner of the hall can modify it."""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.owner == request.user or request.user.role == 'ADMIN'

class IsBookingParticipant(permissions.BasePermission):
    """Allows access only to the customer who booked, the hall owner, or an admin."""
    def has_object_permission(self, request, view, obj):
        return (
            obj.customer == request.user
            or obj.hall.owner == request.user
            or request.user.role == 'ADMIN'
        )
```

---

## 4. Security Hardening Measures

- **Password Policy**: Minimum 8 characters, requiring mixed case, numbers, and special characters. Hashed via Django's PBKDF2/Argon2 password hasher.
- **CSRF Defense**: Enforced via `CSRF_COOKIE_HTTPONLY = False` with `SameSite='Lax'` for single-page applications reading `X-CSRFToken` headers.
- **Rate Limiting**:
  - `POST /api/v1/auth/login/`: 5 attempts / minute per IP.
  - `POST /api/v1/auth/register/`: 3 attempts / hour per IP.
  - `POST /api/v1/bookings/create-intent/`: 10 requests / minute per user.
- **Account State Verification**: Deactivated or suspended users receive immediate token revocation via Redis token blacklisting.
