# Deployment & Infrastructure Architecture

## 1. Containerized Multi-Service Topology

The HallBook platform is fully containerized using Docker and orchestrated via Docker Compose:

```
┌────────────────────────────────────────────────────────┐
│               Host Network (Port 80 / 443)             │
│                      [ Nginx ]                         │
└───────────┬────────────────────────────────┬───────────┘
            │ /api/*, /admin/*               │ /* (Static Single Page App)
┌───────────▼───────────┐        ┌───────────▼───────────┐
│     [ backend ]       │        │     [ frontend ]      │
│  Gunicorn (Port 8000) │        │  Nginx Static Server  │
└─────┬──────┬──────────┘        └───────────────────────┘
      │      │
      │      └──────────────────────────┐
┌─────▼─────────────────┐        ┌──────▼────────────────┐
│     [ postgres ]      │        │       [ redis ]       │
│   PostgreSQL 16 DB    │        │  Redis 7 Cache/Broker │
└───────────────────────┘        └──────┬─────────┬──────┘
                                        │         │
                                 ┌──────▼───┐ ┌───▼────────┐
                                 │[ worker ]│ │  [ beat ]  │
                                 │  Celery  │ │Celery Beat │
                                 └──────────┘ └────────────┘
```

---

## 2. Environment Variables Specification (`.env.example`)

```env
# Application Configuration
ENVIRONMENT=production
DEBUG=False
SECRET_KEY=change-this-to-a-secure-random-64-character-string
ALLOWED_HOSTS=api.hallbook.in,localhost,127.0.0.1
FRONTEND_URL=https://hallbook.in

# Database Configuration
DATABASE_URL=postgresql://hallbook_user:hallbook_secure_password@postgres:5432/hallbook_db

# Redis & Celery
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# Payment Gateway (Razorpay / Stripe)
PAYMENT_GATEWAY_PROVIDER=RAZORPAY
RAZORPAY_KEY_ID=rzp_live_xxxxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
RAZORPAY_WEBHOOK_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx

# Email / Notification Delivery (SMTP / AWS SES)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=SG.xxxxxxxxxxxxxxxxxxxxxxxx
DEFAULT_FROM_EMAIL=HallBook <notifications@hallbook.in>

# Object Storage (AWS S3 / MinIO)
USE_S3_STORAGE=True
AWS_ACCESS_KEY_ID=AKIAxxxxxxxxxxxxxxxx
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_STORAGE_BUCKET_NAME=hallbook-media-prod
AWS_S3_REGION_NAME=ap-south-1

# Monitoring & Observability
SENTRY_DSN=https://xxxxxxxx@sentry.io/xxxxxx
```

---

## 3. Health Checks & Observability Endpoints

- **Liveness Probe**: `GET /api/v1/health/`
  - Returns `{"status": "UP", "timestamp": "2026-08-10T05:45:00Z"}`
- **Readiness Probe**: `GET /api/v1/ready/`
  - Verifies PostgreSQL database connectivity via `connection.ensure_connection()`.
  - Verifies Redis cache ping via `cache.set('health_check', 1, 5)`.
  - Returns HTTP 200 if all services respond; HTTP 503 Service Unavailable otherwise.

---

## 4. Backup & Disaster Recovery Runbook

1. **Automated Daily Backups**:
   - `pg_dump -Fc -h postgres -U hallbook_user hallbook_db > /backups/db_$(date +%F).dump`
   - Dump files uploaded to encrypted offsite cold storage with 30-day lifecycle retention.
2. **Point-in-Time Recovery (PITR)**:
   - PostgreSQL Write-Ahead Logs (WAL) continuously archived to S3 bucket.
3. **Restoration Procedure**:
   ```bash
   pg_restore --clean --no-owner --dbname=hallbook_db /backups/db_target.dump
   python manage.py migrate
   ```
