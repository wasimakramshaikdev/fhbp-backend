#!/usr/bin/env bash
set -e

echo "=== Running Backend System Checks & Migrations ==="
python3 backend/manage.py check
python3 backend/manage.py migrate --check

echo "=== Running Backend Unit, Integration & E2E Acceptance Tests ==="
python3 backend/manage.py test apps.core.e2e_acceptance_tests apps.core.security_tests apps.disputes apps.dashboard apps.payouts apps.reviews apps.favorites apps.notifications apps.payments apps.bookings apps.availability apps.halls apps.accounts apps.core --settings=config.settings.test --noinput

echo "=== Running Frontend Build & Asset Verification ==="
cd frontend
npm run build
cd ..

echo "=== All Foundation Verifications Passed Successfully! ==="
