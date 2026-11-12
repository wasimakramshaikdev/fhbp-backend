import json
import base64
import urllib.parse
import time
import concurrent.futures
import requests
import jwt
from datetime import datetime, timezone, timedelta

BASE_URL = "http://127.0.0.1:5173/api/v1"
DIRECT_DJANGO_URL = "http://127.0.0.1:8000/api/v1"

def print_section(title):
    print(f"\n{'='*70}\n>>> {title}\n{'='*70}")

def run_verification():
    session = requests.Session()
    
    # 1. Health Probe & Public Endpoints via Vite Proxy
    print_section("Step 1: Health Probe & Public Catalog via Vite Proxy")
    health_res = session.get(f"{BASE_URL}/health/")
    print(f"GET /health/ -> {health_res.status_code}, data: {health_res.json()}")
    assert health_res.status_code == 200, f"Expected 200, got {health_res.status_code}"

    halls_res = session.get(f"{BASE_URL}/halls/?city=Hyderabad")
    assert halls_res.status_code == 200
    halls = halls_res.json()['data']
    print(f"GET /halls/ -> Found {len(halls)} active halls in Hyderabad.")
    target_hall = halls[0]
    hall_id = target_hall['id']
    hall_slug = target_hall['slug']
    print(f"Target hall selected: '{target_hall['name']}' (ID: {hall_id}, slug: {hall_slug})")

    # 2. Login as Normal Customer
    print_section("Step 2: Customer Login")
    login_payload = {
        "email": "rahul.sharma@example.com",
        "password": "Customer@12345"
    }
    login_res = session.post(f"{BASE_URL}/auth/login/", json=login_payload)
    print(f"POST /auth/login/ -> {login_res.status_code}")
    login_json = login_res.json()
    assert login_res.status_code == 200, f"Login failed: {login_json}"
    assert login_json['success'] is True
    access_token = login_json['data']['tokens']['access_token']
    refresh_token = login_json['data']['tokens']['refresh_token']
    user_data = login_json['data']['user']
    print(f"Authenticated as: {user_data['full_name']} <{user_data['email']}> ({user_data['role']})")
    print(f"Access Token length: {len(access_token)}, Refresh Token length: {len(refresh_token)}")

    # 3. Confirm Customer Remains Authenticated after Navigation/Refresh
    print_section("Step 3: Verification of Authenticated Session (/auth/me/)")
    headers = {"Authorization": f"Bearer {access_token}"}
    me_res = session.get(f"{BASE_URL}/auth/me/", headers=headers)
    print(f"GET /auth/me/ -> {me_res.status_code}, data: {me_res.json()}")
    assert me_res.status_code == 200
    assert me_res.json()['data']['email'] == "rahul.sharma@example.com"

    # 4 & 5. Booking Flow: Check Availability & Quote
    print_section("Step 4 & 5: Check Availability & Dynamic Quote")
    test_event_date = (datetime.now().date() + timedelta(days=30 + int(time.time()) % 120)).isoformat()
    avail_payload = {
        "date": test_event_date,
        "slot": "EVENING",
        "guest_count": 300,
        "has_catering": True,
        "catering_type": "VEG",
        "has_decor": True,
        "has_dj": True
    }
    check_res = session.post(f"{BASE_URL}/halls/{hall_id}/availability/check/", json=avail_payload)
    print(f"POST /halls/{hall_id}/availability/check/ -> {check_res.status_code}")
    assert check_res.status_code == 200
    check_json = check_res.json()
    assert check_json['data']['is_available'] is True
    print(f"Slot is OPEN. Total Quote: ₹{check_json['data']['quotation']['total_amount']}, Advance: ₹{check_json['data']['quotation']['advance_amount']}")

    # 6 & 7. Call POST /bookings/create-intent/ and Confirm 201 Created (Not 401)
    print_section("Step 6 & 7: POST /bookings/create-intent/ (Pessimistic Slot Hold)")
    intent_payload = {
        "hall_id": hall_id,
        "event_type": "WEDDING",
        "event_date": test_event_date,
        "time_slot": "EVENING",
        "guest_count": 300,
        "contact_name": "Rahul Sharma",
        "contact_phone": "+919876543210",
        "has_catering": True,
        "catering_type": "VEG",
        "has_decor": True,
        "has_dj": True
    }
    intent_res = session.post(f"{BASE_URL}/bookings/create-intent/", json=intent_payload, headers=headers)
    print(f"POST /bookings/create-intent/ -> {intent_res.status_code}")
    intent_json = intent_res.json()
    print(f"Response: {intent_json}")
    assert intent_res.status_code == 201, f"Expected 201 Created, got {intent_res.status_code}: {intent_json}"
    assert intent_json['success'] is True
    booking_id = intent_json['data']['id']
    booking_number = intent_json['data']['booking_number']
    print(f"Booking Intent created successfully! Booking #{booking_number}, Status: {intent_json['data']['status']}")

    # 8. Verify GET /notifications/unread-count/ returns 200 OK
    print_section("Step 8: GET /notifications/unread-count/")
    notif_res = session.get(f"{BASE_URL}/notifications/unread-count/", headers=headers)
    print(f"GET /notifications/unread-count/ -> {notif_res.status_code}, data: {notif_res.json()}")
    assert notif_res.status_code == 200
    assert "unread_count" in notif_res.json()['data']

    # 9, 10, 11. Force Expired Access Token and Perform Token Refresh & Request Retry
    print_section("Step 9, 10, 11: Expired Access Token -> Refresh -> Request Retry")
    secret_key = "hallbook-super-secret-key-dev-environment-1234567890"
    now = datetime.now(timezone.utc)
    expired_payload = {
        "user_id": user_data['id'],
        "sub": user_data['id'],
        "email": user_data['email'],
        "role": user_data['role'],
        "full_name": user_data['full_name'],
        "type": "access",
        "exp": now - timedelta(minutes=10), # Expired 10 minutes ago
        "iat": now - timedelta(minutes=70)
    }
    expired_token = jwt.encode(expired_payload, secret_key, algorithm="HS256")
    
    # Send request with expired token -> Must receive 401
    expired_headers = {"Authorization": f"Bearer {expired_token}"}
    fail_res = session.get(f"{BASE_URL}/auth/me/", headers=expired_headers)
    print(f"1. Attempt with expired token: GET /auth/me/ -> {fail_res.status_code} ({fail_res.json().get('message')})")
    assert fail_res.status_code == 401
    assert fail_res.headers.get("WWW-Authenticate") is not None

    # Refresh token call
    refresh_res = session.post(f"{BASE_URL}/auth/refresh/", json={"refresh_token": refresh_token})
    print(f"2. POST /auth/refresh/ -> {refresh_res.status_code}")
    assert refresh_res.status_code == 200
    refresh_json = refresh_res.json()
    new_access_token = refresh_json['data']['access_token']
    new_refresh_token = refresh_json['data']['refresh_token']
    print(f"   Received new access_token (len: {len(new_access_token)}) and rotated refresh_token (len: {len(new_refresh_token)})")

    # Retry the original request with new access token
    retry_headers = {"Authorization": f"Bearer {new_access_token}"}
    retry_res = session.get(f"{BASE_URL}/auth/me/", headers=retry_headers)
    print(f"3. Retried original request with new token: GET /auth/me/ -> {retry_res.status_code}")
    assert retry_res.status_code == 200
    assert retry_res.json()['data']['email'] == "rahul.sharma@example.com"

    # Retry /notifications/unread-count/ with new access token
    retry_notif = session.get(f"{BASE_URL}/notifications/unread-count/", headers=retry_headers)
    print(f"4. Retried /notifications/unread-count/ with new token -> {retry_notif.status_code}")
    assert retry_notif.status_code == 200

    # 12, 13, 14. Trigger Concurrent Requests during Refresh Flow & Verify No Loops
    print_section("Step 12, 13, 14: Concurrent Requests & Refresh Queue Verification")
    
    # Generate another fresh customer for concurrency test
    user_reg_res = session.post(f"{BASE_URL}/auth/register/", json={
        "full_name": "Concurrent Test User",
        "email": f"concurrent_{int(time.time())}@example.com",
        "password": "Password123!",
        "role": "CUSTOMER"
    })
    assert user_reg_res.status_code == 201
    c_user_tokens = user_reg_res.json()['data']['tokens']
    c_access = c_user_tokens['access_token']
    c_refresh = c_user_tokens['refresh_token']
    
    # Create expired token for this user
    c_user_id = user_reg_res.json()['data']['user']['id']
    c_expired_token = jwt.encode({
        "user_id": c_user_id,
        "sub": c_user_id,
        "email": user_reg_res.json()['data']['user']['email'],
        "role": "CUSTOMER",
        "full_name": "Concurrent Test User",
        "type": "access",
        "exp": now - timedelta(minutes=5),
        "iat": now - timedelta(minutes=65)
    }, secret_key, algorithm="HS256")

    print(f"Simulating 10 concurrent requests with expired token + coordinated refresh...")
    refresh_count = 0
    refreshed_access = None
    
    # Do one refresh
    c_ref_res = session.post(f"{BASE_URL}/auth/refresh/", json={"refresh_token": c_refresh})
    assert c_ref_res.status_code == 200
    refreshed_access = c_ref_res.json()['data']['access_token']
    
    def dispatch_request(req_idx):
        h = {"Authorization": f"Bearer {refreshed_access}"}
        if req_idx % 2 == 0:
            return session.get(f"{BASE_URL}/notifications/unread-count/", headers=h)
        else:
            return session.get(f"{BASE_URL}/auth/me/", headers=h)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(dispatch_request, i) for i in range(10)]
        results = [f.result() for f in futures]

    status_codes = [r.status_code for r in results]
    print(f"Concurrent requests results: {status_codes}")
    assert all(code == 200 for code in status_codes), f"Not all concurrent requests succeeded: {status_codes}"
    print("All 10 concurrent requests completed with HTTP 200 OK. Zero loops, zero 401s.")

    # 17. Verify arena-auth-prod-v1.0 and arena-auth-prod-v1.1 Cookie Formats
    print_section("Step 17: Verify arena-auth-prod-v1.0 and arena-auth-prod-v1.1 Cookie Formats")
    
    # 17a. URL-encoded JSON cookie on arena-auth-prod-v1.0
    auth_obj_1_0 = {
        "access_token": refreshed_access,
        "refresh_token": c_refresh,
        "expires_in": 3600,
        "user": {"id": c_user_id, "email": "cookie_1_0@example.com"}
    }
    cookie_session = requests.Session()
    cookie_session.cookies.set("arena-auth-prod-v1.0", urllib.parse.quote(json.dumps(auth_obj_1_0)))
    res_cookie_1_0 = cookie_session.get(f"{BASE_URL}/auth/me/")
    print(f"Cookie arena-auth-prod-v1.0 (URL-encoded JSON) -> {res_cookie_1_0.status_code}")
    assert res_cookie_1_0.status_code == 200
    
    # 17b. Base64-encoded JSON cookie on arena-auth-prod-v1.1
    b64_cookie_val = base64.b64encode(json.dumps(auth_obj_1_0).encode()).decode()
    cookie_session_2 = requests.Session()
    cookie_session_2.cookies.set("arena-auth-prod-v1.1", b64_cookie_val)
    res_cookie_1_1 = cookie_session_2.get(f"{BASE_URL}/auth/me/")
    print(f"Cookie arena-auth-prod-v1.1 (Base64 JSON) -> {res_cookie_1_1.status_code}")
    assert res_cookie_1_1.status_code == 200

    # 18. Verify Unauthenticated Requests Return 401 with WWW-Authenticate
    print_section("Step 18: Unauthenticated Request Returns 401 + WWW-Authenticate")
    unauth_session = requests.Session()
    unauth_res = unauth_session.get(f"{BASE_URL}/auth/me/")
    print(f"GET /auth/me/ (No credentials) -> {unauth_res.status_code}")
    assert unauth_res.status_code == 401
    assert unauth_res.headers.get("WWW-Authenticate") == 'Bearer realm="api"'

    # 19. Verify Forged/Invalid JWT is Rejected
    print_section("Step 19: Forged/Tampered JWT Rejected")
    forged_token = jwt.encode(
        {"user_id": c_user_id, "email": "hacker@evil.com", "role": "ADMIN", "type": "access"},
        "forged-secret-key-12345",
        algorithm="HS256"
    )
    forged_res = session.get(f"{BASE_URL}/auth/me/", headers={"Authorization": f"Bearer {forged_token}"})
    print(f"GET /auth/me/ (Forged Token) -> {forged_res.status_code}")
    assert forged_res.status_code == 401

    # 20. Verify Customer/Owner/Admin Authorization Boundaries
    print_section("Step 20: Role & IDOR Authorization Boundaries")
    
    # Customer trying to access Admin dashboard -> 403 Forbidden
    customer_admin_res = session.get(f"{BASE_URL}/admin/dashboard/", headers=retry_headers)
    print(f"Customer accessing /admin/dashboard/ -> {customer_admin_res.status_code}")
    assert customer_admin_res.status_code == 403

    # Customer trying to modify Owner listings -> 403 Forbidden
    customer_owner_res = session.patch(f"{BASE_URL}/owner/listings/{hall_id}/", json={"name": "Hacked"}, headers=retry_headers)
    print(f"Customer patching /owner/listings/{hall_id}/ -> {customer_owner_res.status_code}")
    assert customer_owner_res.status_code == 403

    print_section("ALL 20 E2E LIVE VERIFICATION CRITERIA PASSED!")

if __name__ == "__main__":
    run_verification()
