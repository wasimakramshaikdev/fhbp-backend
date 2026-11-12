# HALLBOOK — Function Hall Booking Marketplace

HallBook is a production-grade Function Hall Booking Platform connecting customers searching for banquet halls, convention centers, and lawns with venue owners and platform administrators.

---

## 1. Technology Stack

- **Frontend**: React 18, Tailwind CSS (v4), React Router 6, Axios, Lucide React Icons, Vite
- **Backend API**: Python 3.13, Django 5/6, Django REST Framework, drf-spectacular (OpenAPI 3)
- **Primary Database**: PostgreSQL 16/17 (Authoritative ACID data store, row-level locking)
- **Caching & Broker**: Redis 7
- **Background Processing**: Celery & Celery Beat
- **Containerization**: Docker, Docker Compose, Nginx Reverse Proxy

---

## 2. Architecture & High-Level Principles

- **Modular Monolith**: Clean separation between `accounts`, `halls`, `availability`, `bookings`, `payments`, `reviews`, `favorites`, `notifications`, `disputes`, `payouts`, and `core`.
- **Zero Double-Booking Guarantee**: Concurrency-safe pessimistic locking (`select_for_update`) during checkout.
- **Strict Monetary Precision**: Decimal arithmetic with no floating-point rounding errors.
- **Role-Based & Object-Level Access Control**: Distinct capabilities for `CUSTOMER`, `OWNER`, and `ADMIN`.

---

## 3. Quickstart & Local Development

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL 16+
- Redis 7+

### 1. Database & Cache Setup
```bash
# Start PostgreSQL & Redis services
sudo service postgresql start
sudo service redis-server start

# Create Database and User
sudo -u postgres psql -c "CREATE USER hallbook_user WITH PASSWORD 'hallbook_secure_password' CREATEDB SUPERUSER;"
sudo -u postgres psql -c "CREATE DATABASE hallbook_db OWNER hallbook_user;"
```

### 2. Backend Setup
```bash
pip install -r requirements.txt
python backend/manage.py migrate
python backend/manage.py test
python backend/manage.py runserver 0.0.0.0:8000
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run build
npm run dev -- --host 0.0.0.0 --port 5173
```

---

## 4. Health Checks & API Documentation
- **Liveness Probe**: `GET /api/v1/health/`
- **Readiness Probe**: `GET /api/v1/ready/`
- **Interactive OpenAPI 3 / Swagger**: `GET /api/docs/`
- **Redoc Specification**: `GET /api/redoc/`
