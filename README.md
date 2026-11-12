# Potla EventSpaces — Backend API & Infrastructure

Production-grade Django REST Framework backend and containerized infrastructure for the Potla EventSpaces function hall booking platform.

---

## 1. Technology Stack

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

### Option A: Run via Docker Compose (Recommended)
```bash
docker compose up --build
```

### Option B: Manual Local Setup

#### Prerequisites
- Python 3.11+
- PostgreSQL 16+
- Redis 7+

#### 1. Database & Cache Setup
```bash
# Start PostgreSQL & Redis services
sudo service postgresql start
sudo service redis-server start

# Create Database and User
sudo -u postgres psql -c "CREATE USER hallbook_user WITH PASSWORD 'hallbook_secure_password' CREATEDB SUPERUSER;"
sudo -u postgres psql -c "CREATE DATABASE hallbook_db OWNER hallbook_user;"
```

#### 2. Backend Setup
```bash
pip install -r requirements.txt
python backend/manage.py migrate
python backend/manage.py test
python backend/manage.py runserver 0.0.0.0:8000
```

---

## 4. Health Checks & API Documentation
- **Liveness Probe**: `GET /api/v1/health/`
- **Readiness Probe**: `GET /api/v1/ready/`
- **Interactive OpenAPI 3 / Swagger**: `GET /api/docs/`
- **Redoc Specification**: `GET /api/redoc/`

---
*Looking for the React client application? Check the [`fhbp-frontend`](https://github.com/wasimakramshaikdev/fhbp-frontend) repository.*
