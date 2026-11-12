# Security & Fraud Prevention Strategy

## 1. Threat Modeling & Defense Strategies

| Threat / Vulnerability | Risk | Mitigation Architecture |
|---|---|---|
| **Insecure Direct Object Reference (IDOR)** | Critical | All primary models use non-enumerable UUIDv4 keys. Serializers and views enforce object-level authorization (`IsBookingParticipant`, `IsHallOwner`, `IsReviewAuthor`). |
| **Double Booking Race Conditions** | Critical | PostgreSQL Pessimistic Row Locking (`select_for_update`) inside atomic transactions. Conflict detection checks across morning, evening, and full-day slots. |
| **Payment Webhook Forgery** | High | HMAC SHA-256 cryptographic signature validation against webhook payload; payment idempotency keys with database unique constraints. |
| **Role Escalation / Tampering** | High | Role attributes (`role`, `is_verified`, `approval_status`) are immutable via public API serializers; assigned strictly by backend logic or Super Admin views. |
| **SQL Injection** | High | Exclusive use of parameterized Django ORM queries; no raw SQL formatting or string concatenation. |
| **Cross-Site Scripting (XSS)** | Medium | React JSX automatic string escaping; bleach HTML sanitization on rich-text description inputs; `Content-Security-Policy` HTTP headers. |
| **Cross-Site Request Forgery (CSRF)**| Medium | Strict SameSite cookie policies (`SameSite='Lax'`) and CSRF tokens enforced on state-modifying requests. |
| **Brute Force & Credential Stuffing**| Medium | Redis-backed token bucket rate limiters on `/api/v1/auth/login/` (5 attempts / min) and `/api/v1/auth/register/` (3 / hr). |
| **Malicious File Uploads** | Medium | Validation of file extensions, MIME types using `python-magic`, file size capping (max 5MB/image), and EXIF stripping before S3 storage. |
| **Sensitive PII / Bank Account Exposure**| High | Owner bank account numbers are stored encrypted at rest; masked in API responses (`**** **** 4321`); stripped from system logging. |

---

## 2. Django Production Security Configuration

```python
# config/settings/production.py
DEBUG = False
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # Allows React frontend to read token for headers
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

SECURE_HSTS_SECONDS = 31536000  # 1 Year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    os.getenv('FRONTEND_URL', 'https://hallbook.in'),
]
```

---

## 3. Comprehensive Audit Logging System

Every administrative, listing approval, dispute settlement, and financial payout event creates an immutable entry in the `AuditLog` table:

```python
# apps/core/services/audit.py
class AuditService:
    @staticmethod
    def log_action(actor, action: str, obj, ip_address: str = None, user_agent: str = None, changes: dict = None):
        AuditLog.objects.create(
            actor=actor if actor and actor.is_authenticated else None,
            action=action,
            object_type=obj.__class__.__name__,
            object_id=str(obj.pk),
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else '',
            changes=changes or {}
        )
```
