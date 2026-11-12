import json
import base64
import urllib.parse
from decimal import Decimal
from datetime import date
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, UserRole, OwnerProfile, OwnerVerificationStatus, PasswordResetToken, EmailVerificationToken
from apps.accounts.authentication import JWTTokenService, extract_access_token_from_cookies, extract_refresh_token_from_cookies
from apps.halls.models import Hall, HallApprovalStatus, HallStatus
from apps.notifications.models import Notification, NotificationType

class AuthIntegrationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_customer_registration_success(self):
        payload = {
            "full_name": "Ananya Reddy",
            "email": "ananya@example.com",
            "phone": "+919988776655",
            "password": "SecurePassword123!",
            "role": "CUSTOMER"
        }
        response = self.client.post('/api/v1/auth/register/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['user']['email'], "ananya@example.com")
        self.assertEqual(response.data['data']['user']['role'], "CUSTOMER")
        self.assertIn('access_token', response.data['data']['tokens'])

    def test_owner_registration_creates_owner_profile(self):
        payload = {
            "full_name": "K. Venkatesh",
            "email": "venkatesh@grandorchid.com",
            "phone": "+919876543299",
            "password": "SecurePassword123!",
            "role": "OWNER",
            "business_name": "Grand Orchid Conventions",
            "locality": "Madhapur",
            "city": "Hyderabad"
        }
        response = self.client.post('/api/v1/auth/register/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        
        user = User.objects.get(email="venkatesh@grandorchid.com")
        self.assertTrue(user.is_owner)
        self.assertEqual(user.owner_profile.business_name, "Grand Orchid Conventions")
        self.assertEqual(user.owner_profile.locality, "Madhapur")

    def test_owner_registration_fails_without_business_name(self):
        payload = {
            "full_name": "Owner Without Biz",
            "email": "nobiz@example.com",
            "password": "SecurePassword123!",
            "role": "OWNER"
        }
        response = self.client.post('/api/v1/auth/register/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('business_name', response.data['errors'])

    def test_user_login_success_and_cookie_generation(self):
        user = User.objects.create_user(
            email="loginuser@example.com",
            password="LoginPassword123!",
            full_name="Login Test",
            role=UserRole.CUSTOMER
        )
        response = self.client.post('/api/v1/auth/login/', {
            "email": "loginuser@example.com",
            "password": "LoginPassword123!"
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('access_token', response.data['data']['tokens'])
        self.assertIn('refresh_token', response.cookies)

    def test_user_login_fails_with_wrong_password(self):
        User.objects.create_user(
            email="wrongpass@example.com",
            password="CorrectPassword123!",
            full_name="Wrong Pass User"
        )
        response = self.client.post('/api/v1/auth/login/', {
            "email": "wrongpass@example.com",
            "password": "WrongPassword!"
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['message'], 'Invalid password.')

    def test_user_login_fails_with_unknown_email(self):
        response = self.client.post('/api/v1/auth/login/', {
            "email": "missing@example.com",
            "password": "WrongPassword!"
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['message'], 'Invalid email address.')

    def test_duplicate_email_registration_returns_specific_message(self):
        User.objects.create_user(
            email='duplicate@example.com',
            password='SecurePassword123!',
            full_name='Existing User',
            phone='+919900000001',
        )

        response = self.client.post('/api/v1/auth/register/', {
            'full_name': 'New User',
            'email': 'duplicate@example.com',
            'phone': '+919900000002',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!',
            'role': 'CUSTOMER',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], 'An account with this email address already exists.')

    def test_duplicate_phone_registration_returns_specific_message(self):
        User.objects.create_user(
            email='newuser@example.com',
            password='SecurePassword123!',
            full_name='Existing User',
            phone='+919900000099',
        )

        response = self.client.post('/api/v1/auth/register/', {
            'full_name': 'Another User',
            'email': 'another@example.com',
            'phone': '+919900000099',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!',
            'role': 'CUSTOMER',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], 'An account with this phone number already exists.')

    def test_deactivated_user_cannot_login(self):
        User.objects.create_user(
            email="inactive@example.com",
            password="Password123!",
            full_name="Inactive User",
            is_active=False
        )
        response = self.client.post('/api/v1/auth/login/', {
            "email": "inactive@example.com",
            "password": "Password123!"
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh_lifecycle(self):
        user = User.objects.create_user(
            email="refreshtest@example.com",
            password="Password123!",
            full_name="Refresh Test User"
        )
        tokens = JWTTokenService.generate_tokens_for_user(user)

        response = self.client.post('/api/v1/auth/refresh/', {
            "refresh_token": tokens['refresh_token']
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('access_token', response.data['data'])

        # Previous refresh token should now be revoked
        second_response = self.client.post('/api/v1/auth/refresh/', {
            "refresh_token": tokens['refresh_token']
        }, format='json')
        self.assertEqual(second_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_current_user_profile_and_update(self):
        user = User.objects.create_user(
            email="profiletest@example.com",
            password="Password123!",
            full_name="Original Name",
            phone="+919000000001",
            role=UserRole.OWNER
        )
        OwnerProfile.objects.create(
            user=user,
            business_name="Original Venue",
            city="Hyderabad"
        )
        tokens = JWTTokenService.generate_tokens_for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}")

        # Fetch profile
        get_res = self.client.get('/api/v1/auth/me/')
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data['data']['full_name'], "Original Name")
        self.assertEqual(get_res.data['data']['owner_profile']['business_name'], "Original Venue")

        # Update profile
        patch_res = self.client.patch('/api/v1/auth/me/', {
            "full_name": "Updated Name",
            "business_name": "Updated Venue Name",
            "bank_account_holder": "Updated Venue LLC",
            "bank_account_number": "12345678901234"
        }, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data['data']['full_name'], "Updated Name")
        self.assertEqual(patch_res.data['data']['owner_profile']['business_name'], "Updated Venue Name")
        self.assertEqual(patch_res.data['data']['owner_profile']['masked_bank_account'], "**** **** 1234")

    def test_password_reset_flow(self):
        user = User.objects.create_user(
            email="resetme@example.com",
            password="OldPassword123!",
            full_name="Reset User"
        )

        # Request reset
        req_res = self.client.post('/api/v1/auth/password-reset/', {"email": "resetme@example.com"}, format='json')
        self.assertEqual(req_res.status_code, status.HTTP_200_OK)

        token_obj = PasswordResetToken.objects.filter(user=user, is_used=False).first()
        self.assertIsNotNone(token_obj)

        # Confirm reset
        confirm_res = self.client.post('/api/v1/auth/password-reset/confirm/', {
            "token": token_obj.token,
            "new_password": "NewSecurePassword456!"
        }, format='json')
        self.assertEqual(confirm_res.status_code, status.HTTP_200_OK)

        # Test login with new password
        login_res = self.client.post('/api/v1/auth/login/', {
            "email": "resetme@example.com",
            "password": "NewSecurePassword456!"
        }, format='json')
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)

    def test_email_verification_flow(self):
        user = User.objects.create_user(
            email="unverified@example.com",
            password="Password123!",
            full_name="Unverified User",
            is_verified=False
        )
        token_obj = EmailVerificationToken.create_for_user(user)

        res = self.client.post('/api/v1/auth/verify-email/', {"token": token_obj.token}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        user.refresh_from_db()
        self.assertTrue(user.is_verified)

    def test_login_persists_and_auth_me_succeeds_immediately(self):
        """After login, access token allows immediate /auth/me/ retrieval without 401."""
        user = User.objects.create_user(
            email="persist_test@example.com",
            password="Password123!",
            full_name="Persist User",
            role=UserRole.CUSTOMER
        )
        login_res = self.client.post('/api/v1/auth/login/', {
            "email": "persist_test@example.com",
            "password": "Password123!"
        }, format='json')
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        token = login_res.data['data']['tokens']['access_token']

        # Call /auth/me/ with token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        me_res = self.client.get('/api/v1/auth/me/')
        self.assertEqual(me_res.status_code, status.HTTP_200_OK)
        self.assertEqual(me_res.data['data']['email'], "persist_test@example.com")

    def test_refresh_endpoint_returns_rotated_access_and_refresh_tokens(self):
        """Calling /auth/refresh/ returns new access_token and rotated refresh_token in response data."""
        user = User.objects.create_user(
            email="rotation_test@example.com",
            password="Password123!",
            full_name="Rotation User",
            role=UserRole.CUSTOMER
        )
        tokens = JWTTokenService.generate_tokens_for_user(user)

        refresh_res = self.client.post('/api/v1/auth/refresh/', {
            "refresh_token": tokens['refresh_token']
        }, format='json')
        self.assertEqual(refresh_res.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', refresh_res.data['data'])
        self.assertIn('refresh_token', refresh_res.data['data'])

        # New access token must work on /auth/me/
        new_access = refresh_res.data['data']['access_token']
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access}")
        me_res = self.client.get('/api/v1/auth/me/')
        self.assertEqual(me_res.status_code, status.HTTP_200_OK)
        self.assertEqual(me_res.data['data']['email'], "rotation_test@example.com")

    def test_booking_create_intent_succeeds_immediately_after_refresh(self):
        """Proves POST /bookings/create-intent/ succeeds with 201 using the access token from /auth/refresh/."""
        owner = User.objects.create_user(
            email="owner_create_intent@example.com",
            password="Password123!",
            full_name="Hall Host",
            role=UserRole.OWNER
        )
        OwnerProfile.objects.create(user=owner, business_name="Grand Orchid Conventions", city="Hyderabad")
        hall = Hall.objects.create(
            owner=owner,
            name="Orchid Grand Hall",
            address_line1="Road 36, Madhapur",
            city="Hyderabad",
            locality="Madhapur",
            min_capacity=100,
            max_capacity=500,
            base_price_morning=30000,
            base_price_evening=45000,
            base_price_full_day=70000,
            approval_status=HallApprovalStatus.APPROVED,
            status=HallStatus.ACTIVE
        )

        customer = User.objects.create_user(
            email="cust_booking_refresh@example.com",
            password="Password123!",
            full_name="Booking Customer",
            role=UserRole.CUSTOMER
        )
        init_tokens = JWTTokenService.generate_tokens_for_user(customer)

        # Call refresh endpoint to get new token
        refresh_res = self.client.post('/api/v1/auth/refresh/', {
            "refresh_token": init_tokens['refresh_token']
        }, format='json')
        self.assertEqual(refresh_res.status_code, status.HTTP_200_OK)
        new_access_token = refresh_res.data['data']['access_token']

        # Call /bookings/create-intent/ with refreshed access token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access_token}")
        intent_res = self.client.post('/api/v1/bookings/create-intent/', {
            "hall_id": str(hall.id),
            "event_type": "WEDDING",
            "event_date": "2026-10-15",
            "time_slot": "EVENING",
            "guest_count": 250,
            "contact_name": "Booking Customer",
            "contact_phone": "+919876543210"
        }, format='json')
        self.assertEqual(intent_res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(intent_res.data['success'])
        self.assertEqual(intent_res.data['data']['status'], "PAYMENT_PENDING")

    def test_notification_unread_count_succeeds_immediately_after_refresh(self):
        """Proves GET /notifications/unread-count/ succeeds with 200 using access token from /auth/refresh/."""
        customer = User.objects.create_user(
            email="cust_notif_refresh@example.com",
            password="Password123!",
            full_name="Notification Customer",
            role=UserRole.CUSTOMER
        )
        Notification.objects.create(
            user=customer,
            title="Welcome to HallBook",
            message="Your account is active.",
            type=NotificationType.BOOKING_CREATED
        )
        init_tokens = JWTTokenService.generate_tokens_for_user(customer)

        # Call refresh
        refresh_res = self.client.post('/api/v1/auth/refresh/', {
            "refresh_token": init_tokens['refresh_token']
        }, format='json')
        self.assertEqual(refresh_res.status_code, status.HTTP_200_OK)
        new_access_token = refresh_res.data['data']['access_token']

        # Call /notifications/unread-count/
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access_token}")
        notif_res = self.client.get('/api/v1/notifications/unread-count/')
        self.assertEqual(notif_res.status_code, status.HTTP_200_OK)
        self.assertEqual(notif_res.data['data']['unread_count'], 1)

    def test_authorization_header_variations(self):
        """Tests case-insensitivity, lowercase bearer, and whitespace tolerance in Authorization header."""
        user = User.objects.create_user(
            email="header_test@example.com",
            password="Password123!",
            full_name="Header Test",
            role=UserRole.CUSTOMER
        )
        token = JWTTokenService.generate_tokens_for_user(user)['access_token']

        # 1. Standard: 'Bearer <token>'
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        res1 = self.client.get('/api/v1/auth/me/')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        # 2. Lowercase: 'bearer <token>'
        self.client.credentials(HTTP_AUTHORIZATION=f"bearer {token}")
        res2 = self.client.get('/api/v1/auth/me/')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)

        # 3. Extra whitespace: '  Bearer   <token>  '
        self.client.credentials(HTTP_AUTHORIZATION=f"  Bearer   {token}  ")
        res3 = self.client.get('/api/v1/auth/me/')
        self.assertEqual(res3.status_code, status.HTTP_200_OK)

        # 4. Bare token: '<token>'
        self.client.credentials(HTTP_AUTHORIZATION=token)
        res4 = self.client.get('/api/v1/auth/me/')
        self.assertEqual(res4.status_code, status.HTTP_200_OK)

    def test_all_arena_auth_cookie_formats(self):
        """Verifies raw JWT, JSON, URL-encoded JSON, Base64 JSON, and URL-encoded Base64 JSON in cookies."""
        user = User.objects.create_user(
            email="cookie_formats@example.com",
            password="Password123!",
            full_name="Cookie Formats User",
            role=UserRole.CUSTOMER
        )
        tokens = JWTTokenService.generate_tokens_for_user(user)
        access_token = tokens['access_token']
        refresh_token = tokens['refresh_token']

        auth_dict = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": 3600,
            "user": {"id": str(user.id), "email": user.email}
        }
        json_str = json.dumps(auth_dict)
        url_encoded_json = urllib.parse.quote(json_str)
        b64_json = base64.b64encode(json_str.encode()).decode()
        url_encoded_b64 = urllib.parse.quote(b64_json)

        cookie_variants = [
            ("raw_jwt", access_token),
            ("json", json_str),
            ("url_encoded_json", url_encoded_json),
            ("b64_json", b64_json),
            ("url_encoded_b64", url_encoded_b64),
        ]

        for desc, cookie_val in cookie_variants:
            self.client.credentials()  # Clear Authorization header
            self.client.cookies['arena-auth-prod-v1.0'] = cookie_val
            res = self.client.get('/api/v1/auth/me/')
            self.assertEqual(res.status_code, status.HTTP_200_OK, f"Failed for format: {desc}")
            self.assertEqual(res.data['data']['email'], "cookie_formats@example.com", f"Mismatch for format: {desc}")
