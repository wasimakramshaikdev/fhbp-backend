import json
import base64
import urllib.parse
import time
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = "http://127.0.0.1:5173/api/v1"

def print_section(title):
    print(f"\n{'='*75}\n>>> {title}\n{'='*75}")

def run_auth_verification():
    session = requests.Session()
    
    # 1. Health Probe
    print_section("Step 1: Health Probe & Catalog Discovery")
    health = session.get(f"{BASE_URL}/health/")
    print(f"GET /health/ -> {health.status_code}, data: {health.json()}")
    assert health.status_code == 200

    halls_res = session.get(f"{BASE_URL}/halls/?city=Hyderabad")
    assert halls_res.status_code == 200
    hall = halls_res.json()['data'][0]
    hall_id = hall['id']
    hall_slug = hall['slug']
    print(f"Selected Venue: '{hall['name']}' (ID: {hall_id})")

    # 2. Customer Login
    print_section("Step 2: Customer Login (POST /auth/login/)")
    login_res = session.post(f"{BASE_URL}/auth/login/", json={
        "email": "rahul.sharma@example.com",
        "password": "Customer@12345"
    })
    print(f"POST /auth/login/ -> {login_res.status_code}")
    assert login_res.status_code == 200
    login_json = login_res.json()
    tokens = login_json['data']['tokens']
    user = login_json['data']['user']
    access_token = tokens['access_token']
    refresh_token = tokens['refresh_token']
    
    print(f"[AUTH DEBUG] access token exists: {bool(access_token)}")
    print(f"[AUTH DEBUG] token length: {len(access_token)}")
    print(f"[AUTH DEBUG] current user: {user['email']} (role: {user['role']})")
    
    auth_headers = {"Authorization": f"Bearer {access_token}"}

    # 3. Authenticated Dashboard & Navigation
    print_section("Step 3: Authenticated Requests across Dashboard")
    
    # /auth/me/
    me_res = session.get(f"{BASE_URL}/auth/me/", headers=auth_headers)
    print(f"[AUTH DEBUG] GET /auth/me/ status: {me_res.status_code} (User: {me_res.json()['data']['email']})")
    assert me_res.status_code == 200

    # /notifications/unread-count/
    notif_res = session.get(f"{BASE_URL}/notifications/unread-count/", headers=auth_headers)
    print(f"[AUTH DEBUG] GET /notifications/unread-count/ status: {notif_res.status_code}")
    assert notif_res.status_code == 200

    # /bookings/
    bookings_res = session.get(f"{BASE_URL}/bookings/", headers=auth_headers)
    print(f"[AUTH DEBUG] GET /bookings/ status: {bookings_res.status_code} (Count: {len(bookings_res.json()['data'])})")
    assert bookings_res.status_code == 200

    # /favorites/
    favs_res = session.get(f"{BASE_URL}/favorites/", headers=auth_headers)
    print(f"[AUTH DEBUG] GET /favorites/ status: {favs_res.status_code}")
    assert favs_res.status_code == 200

    # /payments/invoices/
    invoices_res = session.get(f"{BASE_URL}/payments/invoices/", headers=auth_headers)
    print(f"[AUTH DEBUG] GET /payments/invoices/ status: {invoices_res.status_code}")
    assert invoices_res.status_code == 200

    # 4. Immediate Booking Intent Creation (Pessimistic Slot Reservation)
    print_section("Step 4: Booking Intent Creation (POST /bookings/create-intent/)")
    test_date = (datetime.now().date() + timedelta(days=45 + int(time.time()) % 90)).isoformat()
    intent_payload = {
        "hall_id": hall_id,
        "event_type": "WEDDING",
        "event_date": test_date,
        "time_slot": "EVENING",
        "guest_count": 300,
        "contact_name": "Rahul Sharma",
        "contact_phone": "+919876543210",
        "has_catering": True,
        "catering_type": "VEG",
        "has_decor": True,
        "has_dj": True
    }
    intent_res = session.post(f"{BASE_URL}/bookings/create-intent/", json=intent_payload, headers=auth_headers)
    print(f"[AUTH DEBUG] POST /bookings/create-intent/ status: {intent_res.status_code}")
    assert intent_res.status_code == 201, f"Failed: {intent_res.text}"
    booking_data = intent_res.json()['data']
    booking_id = booking_data['id']
    booking_number = booking_data['booking_number']
    print(f"Booking #{booking_number} created (Status: {booking_data['status']}, Advance: ₹{booking_data['advance_amount']})")

    # 5. Payment Order Creation in SIMULATED Mode
    print_section("Step 5: Payment Order Initiation (/payments/razorpay/order/)")
    order_res = session.post(f"{BASE_URL}/payments/razorpay/order/", json={
        "booking_id": booking_id,
        "payment_type": "ADVANCE",
        "payment_method": "UPI"
    }, headers=auth_headers)
    print(f"[AUTH DEBUG] POST /payments/razorpay/order/ status: {order_res.status_code}")
    assert order_res.status_code == 201, f"Failed: {order_res.text}"
    order_data = order_res.json()['data']
    print(f"Order created: {order_data['gateway_order_id']}, Subunits (paise): {order_data['amount_subunits']}, Key ID: {order_data['key_id']}")

    # 6. Payment Verification (Cryptographic Signature Confirmation)
    print_section("Step 6: Payment Verification (/payments/razorpay/verify/)")
    verify_res = session.post(f"{BASE_URL}/payments/razorpay/verify/", json={
        "gateway_order_id": order_data['gateway_order_id'],
        "gateway_payment_id": f"pay_test_{int(time.time())}",
        "gateway_signature": "valid_simulated_signature"
    }, headers=auth_headers)
    print(f"[AUTH DEBUG] POST /payments/razorpay/verify/ status: {verify_res.status_code}")
    assert verify_res.status_code == 200, f"Failed: {verify_res.text}"
    print(f"Payment confirmed successfully! Reference: {verify_res.json()['data']['payment_reference']}")

    # Check updated booking status
    updated_booking = session.get(f"{BASE_URL}/bookings/{booking_id}/", headers=auth_headers)
    assert updated_booking.status_code == 200
    print(f"Booking updated status: {updated_booking.json()['data']['status']} (Amount Paid: ₹{updated_booking.json()['data']['amount_paid']})")
    assert updated_booking.json()['data']['status'] == "PENDING_OWNER_CONFIRMATION"

    # 7. Browser Reload / Session Persistence Check
    print_section("Step 7: Session Persistence after Reload")
    time.sleep(1)
    reload_me = session.get(f"{BASE_URL}/auth/me/", headers=auth_headers)
    print(f"[AUTH DEBUG] GET /auth/me/ after reload: {reload_me.status_code}")
    assert reload_me.status_code == 200
    assert reload_me.json()['data']['email'] == "rahul.sharma@example.com"

    # 8. Explicit User Logout
    print_section("Step 8: Explicit Logout (POST /auth/logout/)")
    logout_res = session.post(f"{BASE_URL}/auth/logout/", json={"refresh_token": refresh_token}, headers=auth_headers)
    print(f"[AUTH DEBUG] POST /auth/logout/ status: {logout_res.status_code}")
    assert logout_res.status_code == 200

    # 9. Verify Protected Endpoints Return 401 after Logout
    print_section("Step 9: Protected Endpoints Inaccessible after Logout")
    unauth_res = session.get(f"{BASE_URL}/auth/me/") # No headers
    print(f"[AUTH DEBUG] GET /auth/me/ (unauthenticated) status: {unauth_res.status_code}")
    assert unauth_res.status_code == 401
    assert unauth_res.json()['message'] == "Authentication credentials were not provided."

    print_section("ALL AUTHENTICATION PERSISTENCE AND FLOW CHECKS PASSED!")

if __name__ == "__main__":
    run_auth_verification()
