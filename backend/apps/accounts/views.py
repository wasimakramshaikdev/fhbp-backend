# import logging
# from drf_spectacular.utils import extend_schema
# from django.core.cache import cache
# from django.conf import settings
# from rest_framework.views import APIView
# from rest_framework.permissions import AllowAny, IsAuthenticated
# from rest_framework import status
# from apps.core.responses import api_response
# from apps.core.services.audit import AuditService
# from apps.accounts.models import User, PasswordResetToken, EmailVerificationToken
# from apps.accounts.serializers import (
#     UserRegistrationSerializer,
#     UserLoginSerializer,
#     UserProfileSerializer,
#     UserProfileUpdateSerializer,
#     PasswordResetRequestSerializer,
#     PasswordResetConfirmSerializer,
#     EmailVerificationSerializer
# )
# from apps.accounts.authentication import JWTTokenService

# logger = logging.getLogger(__name__)

# def check_rate_limit(request, action_key: str, max_attempts: int = 5, window_seconds: int = 60) -> bool:
#     """Helper to enforce Redis-backed rate limiting per client IP."""
#     ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '127.0.0.1')).split(',')[0].strip()
#     cache_key = f"ratelimit:{action_key}:{ip}"
#     attempts = cache.get(cache_key, 0)
#     if attempts >= max_attempts:
#         return False
#     cache.set(cache_key, attempts + 1, timeout=window_seconds)
#     return True


# class RegisterView(APIView):
#     """
#     Public registration endpoint for Customers and Hall Owners.
#     Automatically provisions OwnerProfile for owners.
#     """
#     permission_classes = [AllowAny]
#     authentication_classes = []

#     def post(self, request):
#         if not check_rate_limit(request, 'register', max_attempts=10, window_seconds=300):
#             return api_response(
#                 message="Too many registration attempts. Please try again in a few minutes.",
#                 status_code=status.HTTP_429_TOO_MANY_REQUESTS,
#                 success=False,
#                 code="RATE_LIMIT_EXCEEDED"
#             )

#         serializer = UserRegistrationSerializer(data=request.data)
#         if not serializer.is_valid():
#             return api_response(
#                 message="Registration validation failed.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="VALIDATION_ERROR"
#             )

#         user = serializer.save()
#         tokens = JWTTokenService.generate_tokens_for_user(user)
#         user_data = UserProfileSerializer(user).data

#         AuditService.log_action(
#             actor=user,
#             action="USER_REGISTERED",
#             obj=user,
#             ip_address=request.META.get('REMOTE_ADDR'),
#             changes={"email": user.email, "role": user.role}
#         )

#         response = api_response(
#             data={
#                 "user": user_data,
#                 "tokens": tokens,
#                 "access_token": tokens['access_token'],
#                 "refresh_token": tokens['refresh_token'],
#                 "expires_in": tokens['expires_in'],
#             },
#             message="Account registered successfully.",
#             status_code=status.HTTP_201_CREATED
#         )

#         # Set secure HttpOnly refresh cookie
#         response.set_cookie(
#             key='refresh_token',
#             value=tokens['refresh_token'],
#             httponly=True,
#             secure=not settings.DEBUG,
#             samesite='Lax',
#             max_age=7 * 24 * 60 * 60  # 7 days
#         )

#         return response


# class LoginView(APIView):
#     """
#     Email & password authentication returning JWT access token and setting HttpOnly refresh cookie.
#     """
#     permission_classes = [AllowAny]
#     authentication_classes = []
#     @extend_schema(
#         request=UserLoginSerializer,
#         responses=UserProfileSerializer,
#         tags=['Authentication'],
#         summary='Login',
#         description='Authenticate a user with email and password.'
#     )

#     def post(self, request):
#         if not check_rate_limit(request, 'login', max_attempts=8, window_seconds=60):
#             return api_response(
#                 message="Too many login attempts. Please wait 60 seconds before trying again.",
#                 status_code=status.HTTP_429_TOO_MANY_REQUESTS,
#                 success=False,
#                 code="RATE_LIMIT_EXCEEDED"
#             )

#         serializer = UserLoginSerializer(data=request.data)
#         if not serializer.is_valid():
#             return api_response(
#                 message="Invalid email or password.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 success=False,
#                 code="AUTHENTICATION_FAILED"
#             )

#         user = serializer.validated_data['user']
#         tokens = JWTTokenService.generate_tokens_for_user(user)
#         user_data = UserProfileSerializer(user).data

#         AuditService.log_action(
#             actor=user,
#             action="USER_LOGGED_IN",
#             obj=user,
#             ip_address=request.META.get('REMOTE_ADDR')
#         )

#         response = api_response(
#             data={
#                 "user": user_data,
#                 "tokens": tokens,
#                 "access_token": tokens['access_token'],
#                 "refresh_token": tokens['refresh_token'],
#                 "expires_in": tokens['expires_in'],
#             },
#             message="Logged in successfully."
#         )

#         response.set_cookie(
#             key='refresh_token',
#             value=tokens['refresh_token'],
#             httponly=True,
#             secure=not settings.DEBUG,
#             samesite='Lax',
#             max_age=7 * 24 * 60 * 60
#         )

#         return response


# class RefreshTokenView(APIView):
#     """
#     Rotates refresh token and returns a new Access Token.
#     Accepts token from HttpOnly cookie or request payload.
#     """
#     permission_classes = [AllowAny]
#     authentication_classes = []

#     def post(self, request):
#         from apps.accounts.authentication import extract_refresh_token_from_cookies
#         refresh_token = (
#             request.data.get('refresh_token')
#             or extract_refresh_token_from_cookies(request.COOKIES)
#             or request.COOKIES.get('refresh_token')
#         )
#         if not refresh_token:
#             return api_response(
#                 message="Refresh token is required.",
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="MISSING_TOKEN"
#             )

#         try:
#             payload = JWTTokenService.decode_token(refresh_token, expected_type='refresh')
#             user_id = payload.get('user_id') or payload.get('sub') or payload.get('id')
#             email = payload.get('email') or payload.get('user_email')

#             user = None
#             if user_id:
#                 try:
#                     user = User.objects.get(id=user_id, is_active=True)
#                 except (User.DoesNotExist, ValueError):
#                     pass

#             if not user and email:
#                 try:
#                     user = User.objects.get(email=email, is_active=True)
#                 except User.DoesNotExist:
#                     pass

#             if not user:
#                 raise AuthenticationFailed('User not found or deactivated.')

#             # Invalidate old refresh token
#             JWTTokenService.revoke_refresh_token(refresh_token, user)

#             # Generate new token pair
#             new_tokens = JWTTokenService.generate_tokens_for_user(user)

#             response = api_response(
#                 data={
#                     "access_token": new_tokens['access_token'],
#                     "refresh_token": new_tokens['refresh_token'],
#                     "tokens": new_tokens,
#                     "expires_in": new_tokens['expires_in'],
#                 },
#                 message="Token refreshed successfully."
#             )

#             response.set_cookie(
#                 key='refresh_token',
#                 value=new_tokens['refresh_token'],
#                 httponly=True,
#                 secure=not settings.DEBUG,
#                 samesite='Lax',
#                 max_age=7 * 24 * 60 * 60
#             )

#             return response
#         except Exception as exc:
#             return api_response(
#                 message="Invalid or expired refresh token.",
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 success=False,
#                 code="INVALID_REFRESH_TOKEN"
#             )


# class LogoutView(APIView):
#     """
#     Revokes the active refresh token and clears session cookies.
#     """
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         refresh_token = request.COOKIES.get('refresh_token') or request.data.get('refresh_token')
#         if refresh_token:
#             JWTTokenService.revoke_refresh_token(refresh_token, request.user)

#         AuditService.log_action(
#             actor=request.user,
#             action="USER_LOGGED_OUT",
#             obj=request.user,
#             ip_address=request.META.get('REMOTE_ADDR')
#         )

#         response = api_response(message="Logged out successfully.")
#         response.delete_cookie('refresh_token')
#         response.delete_cookie('access_token')
#         return response


# class CurrentUserView(APIView):
#     """
#     Retrieves or updates current authenticated user profile.
#     """
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         serializer = UserProfileSerializer(request.user)
#         return api_response(data=serializer.data)

#     def patch(self, request):
#         serializer = UserProfileUpdateSerializer(data=request.data)
#         if not serializer.is_valid():
#             return api_response(
#                 message="Profile update validation failed.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="VALIDATION_ERROR"
#             )

#         updated_user = serializer.update(request.user, serializer.validated_data)
#         return api_response(
#             data=UserProfileSerializer(updated_user).data,
#             message="Profile updated successfully."
#         )


# class PasswordResetRequestView(APIView):
#     """
#     Initiates password recovery by issuing a single-use secure reset token.
#     """
#     permission_classes = [AllowAny]
#     authentication_classes = []

#     def post(self, request):
#         serializer = PasswordResetRequestSerializer(data=request.data)
#         if not serializer.is_valid():
#             return api_response(
#                 message="Invalid email address.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False
#             )

#         email = serializer.validated_data['email']
#         user = User.objects.filter(email=email, is_active=True).first()

#         # Always return success to prevent user email enumeration
#         if user:
#             reset_token = PasswordResetToken.create_for_user(user)
#             logger.info(f"Password reset token for {user.email}: {reset_token.token}")

#         return api_response(
#             message="If an account with this email exists, a password reset link has been sent."
#         )


# class PasswordResetConfirmView(APIView):
#     """
#     Completes password reset using verified single-use token.
#     """
#     permission_classes = [AllowAny]
#     authentication_classes = []

#     def post(self, request):
#         serializer = PasswordResetConfirmSerializer(data=request.data)
#         if not serializer.is_valid():
#             return api_response(
#                 message="Password reset validation failed.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="VALIDATION_ERROR"
#             )

#         token_str = serializer.validated_data['token']
#         new_password = serializer.validated_data['new_password']

#         try:
#             token_obj = PasswordResetToken.objects.get(token=token_str)
#             if not token_obj.is_valid:
#                 return api_response(
#                     message="Password reset token has expired or has already been used.",
#                     status_code=status.HTTP_400_BAD_REQUEST,
#                     success=False,
#                     code="TOKEN_EXPIRED"
#                 )

#             user = token_obj.user
#             user.set_password(new_password)
#             user.save()

#             token_obj.is_used = True
#             token_obj.save()

#             AuditService.log_action(
#                 actor=user,
#                 action="PASSWORD_RESET_COMPLETED",
#                 obj=user,
#                 ip_address=request.META.get('REMOTE_ADDR')
#             )

#             return api_response(message="Password reset successfully. You may now sign in with your new password.")
#         except PasswordResetToken.DoesNotExist:
#             return api_response(
#                 message="Invalid password reset token.",
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="INVALID_TOKEN"
#             )


# class VerifyEmailView(APIView):
#     """
#     Verifies user email address using single-use email verification token.
#     """
#     permission_classes = [AllowAny]
#     authentication_classes = []

#     def post(self, request):
#         serializer = EmailVerificationSerializer(data=request.data)
#         if not serializer.is_valid():
#             return api_response(
#                 message="Token is required.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False
#             )

#         token_str = serializer.validated_data['token']
#         try:
#             token_obj = EmailVerificationToken.objects.get(token=token_str)
#             if not token_obj.is_valid:
#                 return api_response(
#                     message="Email verification token has expired or already used.",
#                     status_code=status.HTTP_400_BAD_REQUEST,
#                     success=False,
#                     code="TOKEN_EXPIRED"
#                 )

#             user = token_obj.user
#             user.is_verified = True
#             user.save()

#             token_obj.is_used = True
#             token_obj.save()

#             return api_response(message="Email verified successfully.")
#         except EmailVerificationToken.DoesNotExist:
#             return api_response(
#                 message="Invalid verification token.",
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="INVALID_TOKEN"
#             )





# import logging

# from django.conf import settings
# from django.core.cache import cache

# from rest_framework import serializers, status
# from rest_framework.exceptions import AuthenticationFailed
# from rest_framework.permissions import AllowAny, IsAuthenticated
# from rest_framework.views import APIView

# from drf_spectacular.utils import (
#     extend_schema,
#     inline_serializer,
# )

# from apps.core.responses import api_response
# from apps.core.services.audit import AuditService

# from apps.accounts.models import (
#     User,
#     PasswordResetToken,
#     EmailVerificationToken,
# )

# from apps.accounts.serializers import (
#     UserRegistrationSerializer,
#     UserLoginSerializer,
#     UserProfileSerializer,
#     UserProfileUpdateSerializer,
#     PasswordResetRequestSerializer,
#     PasswordResetConfirmSerializer,
#     EmailVerificationSerializer,
# )

# from apps.accounts.authentication import JWTTokenService


# logger = logging.getLogger(__name__)


# # ============================================================================
# # OPENAPI RESPONSE SERIALIZERS
# # ============================================================================

# TokenResponseSerializer = inline_serializer(
#     name='TokenResponse',
#     fields={
#         'access_token': serializers.CharField(),
#         'refresh_token': serializers.CharField(),
#         'expires_in': serializers.IntegerField(),
#     },
# )


# AuthResponseSerializer = inline_serializer(
#     name='AuthResponse',
#     fields={
#         'user': UserProfileSerializer(),
#         'tokens': TokenResponseSerializer,
#         'access_token': serializers.CharField(),
#         'refresh_token': serializers.CharField(),
#         'expires_in': serializers.IntegerField(),
#     },
# )


# RefreshTokenResponseSerializer = inline_serializer(
#     name='RefreshTokenResponse',
#     fields={
#         'access_token': serializers.CharField(),
#         'refresh_token': serializers.CharField(),
#         'tokens': TokenResponseSerializer,
#         'expires_in': serializers.IntegerField(),
#     },
# )


# MessageResponseSerializer = inline_serializer(
#     name='MessageResponse',
#     fields={
#         'message': serializers.CharField(),
#     },
# )


# # ============================================================================
# # RATE LIMITING
# # ============================================================================

# def check_rate_limit(
#     request,
#     action_key: str,
#     max_attempts: int = 5,
#     window_seconds: int = 60,
# ) -> bool:
#     """
#     Helper to enforce Redis-backed rate limiting per client IP.
#     """

#     ip = request.META.get(
#         'HTTP_X_FORWARDED_FOR',
#         request.META.get(
#             'REMOTE_ADDR',
#             '127.0.0.1',
#         ),
#     ).split(',')[0].strip()

#     cache_key = f"ratelimit:{action_key}:{ip}"

#     attempts = cache.get(
#         cache_key,
#         0,
#     )

#     if attempts >= max_attempts:
#         return False

#     cache.set(
#         cache_key,
#         attempts + 1,
#         timeout=window_seconds,
#     )

#     return True


# # ============================================================================
# # REGISTER
# # ============================================================================

# class RegisterView(APIView):
#     """
#     Public registration endpoint for Customers and Hall Owners.

#     Automatically provisions OwnerProfile for owners.
#     """

#     permission_classes = [AllowAny]
#     authentication_classes = []

#     @extend_schema(
#         request=UserRegistrationSerializer,
#         responses={
#             201: AuthResponseSerializer,
#             400: MessageResponseSerializer,
#             429: MessageResponseSerializer,
#         },
#         tags=['Authentication'],
#         summary='Register',
#         description=(
#             'Register a new customer or hall owner account. '
#             'Hall owner registration automatically creates an OwnerProfile.'
#         ),
#     )
#     def post(self, request):
#         if not check_rate_limit(
#             request,
#             'register',
#             max_attempts=10,
#             window_seconds=300,
#         ):
#             return api_response(
#                 message=(
#                     "Too many registration attempts. "
#                     "Please try again in a few minutes."
#                 ),
#                 status_code=status.HTTP_429_TOO_MANY_REQUESTS,
#                 success=False,
#                 code="RATE_LIMIT_EXCEEDED",
#             )

#         serializer = UserRegistrationSerializer(
#             data=request.data,
#         )

#         if not serializer.is_valid():
#             return api_response(
#                 message="Registration validation failed.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="VALIDATION_ERROR",
#             )

#         user = serializer.save()

#         tokens = JWTTokenService.generate_tokens_for_user(
#             user,
#         )

#         user_data = UserProfileSerializer(
#             user,
#         ).data

#         AuditService.log_action(
#             actor=user,
#             action="USER_REGISTERED",
#             obj=user,
#             ip_address=request.META.get('REMOTE_ADDR'),
#             changes={
#                 "email": user.email,
#                 "role": user.role,
#             },
#         )

#         response = api_response(
#             data={
#                 "user": user_data,
#                 "tokens": tokens,
#                 "access_token": tokens['access_token'],
#                 "refresh_token": tokens['refresh_token'],
#                 "expires_in": tokens['expires_in'],
#             },
#             message="Account registered successfully.",
#             status_code=status.HTTP_201_CREATED,
#         )

#         response.set_cookie(
#             key='refresh_token',
#             value=tokens['refresh_token'],
#             httponly=True,
#             secure=not settings.DEBUG,
#             samesite='Lax',
#             max_age=7 * 24 * 60 * 60,
#         )

#         return response


# # ============================================================================
# # LOGIN
# # ============================================================================

# class LoginView(APIView):
#     """
#     Email & password authentication returning JWT access token
#     and setting HttpOnly refresh cookie.
#     """

#     permission_classes = [AllowAny]
#     authentication_classes = []

#     @extend_schema(
#         request=UserLoginSerializer,
#         responses={
#             200: AuthResponseSerializer,
#             401: MessageResponseSerializer,
#             429: MessageResponseSerializer,
#         },
#         tags=['Authentication'],
#         summary='Login',
#         description='Authenticate a user with email and password.',
#     )
#     def post(self, request):

#         if not check_rate_limit(
#             request,
#             'login',
#             max_attempts=8,
#             window_seconds=60,
#         ):
#             return api_response(
#                 message=(
#                     "Too many login attempts. "
#                     "Please wait 60 seconds before trying again."
#                 ),
#                 status_code=status.HTTP_429_TOO_MANY_REQUESTS,
#                 success=False,
#                 code="RATE_LIMIT_EXCEEDED",
#             )

#         serializer = UserLoginSerializer(
#             data=request.data,
#         )

#         if not serializer.is_valid():
#             return api_response(
#                 message="Invalid email or password.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 success=False,
#                 code="AUTHENTICATION_FAILED",
#             )

#         user = serializer.validated_data['user']

#         tokens = JWTTokenService.generate_tokens_for_user(
#             user,
#         )

#         user_data = UserProfileSerializer(
#             user,
#         ).data

#         AuditService.log_action(
#             actor=user,
#             action="USER_LOGGED_IN",
#             obj=user,
#             ip_address=request.META.get('REMOTE_ADDR'),
#         )

#         response = api_response(
#             data={
#                 "user": user_data,
#                 "tokens": tokens,
#                 "access_token": tokens['access_token'],
#                 "refresh_token": tokens['refresh_token'],
#                 "expires_in": tokens['expires_in'],
#             },
#             message="Logged in successfully.",
#         )

#         response.set_cookie(
#             key='refresh_token',
#             value=tokens['refresh_token'],
#             httponly=True,
#             secure=not settings.DEBUG,
#             samesite='Lax',
#             max_age=7 * 24 * 60 * 60,
#         )

#         return response


# # ============================================================================
# # REFRESH TOKEN
# # ============================================================================

# class RefreshTokenView(APIView):
#     """
#     Rotates refresh token and returns a new access token.

#     Accepts token from HttpOnly cookie or request payload.
#     """

#     permission_classes = [AllowAny]
#     authentication_classes = []

#     @extend_schema(
#         request=None,
#         responses={
#             200: RefreshTokenResponseSerializer,
#             400: MessageResponseSerializer,
#             401: MessageResponseSerializer,
#         },
#         tags=['Authentication'],
#         summary='Refresh access token',
#         description=(
#             'Rotate the refresh token and return a new access token. '
#             'The refresh token may be supplied in the request body or '
#             'HttpOnly cookie.'
#         ),
#     )
#     def post(self, request):

#         from apps.accounts.authentication import (
#             extract_refresh_token_from_cookies,
#         )

#         refresh_token = (
#             request.data.get('refresh_token')
#             or extract_refresh_token_from_cookies(
#                 request.COOKIES,
#             )
#             or request.COOKIES.get('refresh_token')
#         )

#         if not refresh_token:
#             return api_response(
#                 message="Refresh token is required.",
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="MISSING_TOKEN",
#             )

#         try:

#             payload = JWTTokenService.decode_token(
#                 refresh_token,
#                 expected_type='refresh',
#             )

#             user_id = (
#                 payload.get('user_id')
#                 or payload.get('sub')
#                 or payload.get('id')
#             )

#             email = (
#                 payload.get('email')
#                 or payload.get('user_email')
#             )

#             user = None

#             if user_id:
#                 try:
#                     user = User.objects.get(
#                         id=user_id,
#                         is_active=True,
#                     )
#                 except (
#                     User.DoesNotExist,
#                     ValueError,
#                 ):
#                     pass

#             if not user and email:
#                 try:
#                     user = User.objects.get(
#                         email=email,
#                         is_active=True,
#                     )
#                 except User.DoesNotExist:
#                     pass

#             if not user:
#                 raise AuthenticationFailed(
#                     'User not found or deactivated.'
#                 )

#             # Invalidate old refresh token
#             JWTTokenService.revoke_refresh_token(
#                 refresh_token,
#                 user,
#             )

#             # Generate new token pair
#             new_tokens = JWTTokenService.generate_tokens_for_user(
#                 user,
#             )

#             response = api_response(
#                 data={
#                     "access_token": new_tokens['access_token'],
#                     "refresh_token": new_tokens['refresh_token'],
#                     "tokens": new_tokens,
#                     "expires_in": new_tokens['expires_in'],
#                 },
#                 message="Token refreshed successfully.",
#             )

#             response.set_cookie(
#                 key='refresh_token',
#                 value=new_tokens['refresh_token'],
#                 httponly=True,
#                 secure=not settings.DEBUG,
#                 samesite='Lax',
#                 max_age=7 * 24 * 60 * 60,
#             )

#             return response

#         except Exception as exc:

#             logger.warning(
#                 "Refresh token validation failed: %s",
#                 exc,
#             )

#             return api_response(
#                 message="Invalid or expired refresh token.",
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 success=False,
#                 code="INVALID_REFRESH_TOKEN",
#             )


# # ============================================================================
# # LOGOUT
# # ============================================================================

# class LogoutView(APIView):
#     """
#     Revokes the active refresh token and clears session cookies.
#     """

#     permission_classes = [IsAuthenticated]

#     @extend_schema(
#         request=None,
#         responses={
#             200: MessageResponseSerializer,
#             401: MessageResponseSerializer,
#         },
#         tags=['Authentication'],
#         summary='Logout',
#         description=(
#             'Revoke the current refresh token and clear authentication cookies.'
#         ),
#     )
#     def post(self, request):

#         refresh_token = (
#             request.COOKIES.get('refresh_token')
#             or request.data.get('refresh_token')
#         )

#         if refresh_token:
#             JWTTokenService.revoke_refresh_token(
#                 refresh_token,
#                 request.user,
#             )

#         AuditService.log_action(
#             actor=request.user,
#             action="USER_LOGGED_OUT",
#             obj=request.user,
#             ip_address=request.META.get('REMOTE_ADDR'),
#         )

#         response = api_response(
#             message="Logged out successfully.",
#         )

#         response.delete_cookie(
#             'refresh_token',
#         )

#         response.delete_cookie(
#             'access_token',
#         )

#         return response


# # ============================================================================
# # CURRENT USER
# # ============================================================================

# class CurrentUserView(APIView):
#     """
#     Retrieves or updates current authenticated user profile.
#     """

#     permission_classes = [IsAuthenticated]

#     @extend_schema(
#         request=None,
#         responses={
#             200: UserProfileSerializer,
#             401: MessageResponseSerializer,
#         },
#         tags=['Authentication'],
#         summary='Get current user',
#         description='Retrieve the profile of the currently authenticated user.',
#     )
#     def get(self, request):

#         serializer = UserProfileSerializer(
#             request.user,
#         )

#         return api_response(
#             data=serializer.data,
#         )

#     @extend_schema(
#         request=UserProfileUpdateSerializer,
#         responses={
#             200: UserProfileSerializer,
#             400: MessageResponseSerializer,
#             401: MessageResponseSerializer,
#         },
#         tags=['Authentication'],
#         summary='Update current user',
#         description=(
#             'Update the profile of the currently authenticated user. '
#             'Owner-specific fields can also be updated for hall owners.'
#         ),
#     )
#     def patch(self, request):

#         serializer = UserProfileUpdateSerializer(
#             data=request.data,
#         )

#         if not serializer.is_valid():
#             return api_response(
#                 message="Profile update validation failed.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="VALIDATION_ERROR",
#             )

#         updated_user = serializer.update(
#             request.user,
#             serializer.validated_data,
#         )

#         return api_response(
#             data=UserProfileSerializer(
#                 updated_user,
#             ).data,
#             message="Profile updated successfully.",
#         )


# # ============================================================================
# # PASSWORD RESET REQUEST
# # ============================================================================

# class PasswordResetRequestView(APIView):
#     """
#     Initiates password recovery by issuing a single-use secure reset token.
#     """

#     permission_classes = [AllowAny]
#     authentication_classes = []

#     @extend_schema(
#         request=PasswordResetRequestSerializer,
#         responses={
#             200: MessageResponseSerializer,
#             400: MessageResponseSerializer,
#         },
#         tags=['Authentication'],
#         summary='Request password reset',
#         description=(
#             'Request a password reset link. '
#             'The endpoint intentionally returns the same success response '
#             'whether or not the email exists.'
#         ),
#     )
#     def post(self, request):

#         serializer = PasswordResetRequestSerializer(
#             data=request.data,
#         )

#         if not serializer.is_valid():
#             return api_response(
#                 message="Invalid email address.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#             )

#         email = serializer.validated_data['email']

#         user = User.objects.filter(
#             email=email,
#             is_active=True,
#         ).first()

#         # Always return success to prevent user email enumeration
#         if user:
#             reset_token = PasswordResetToken.create_for_user(
#                 user,
#             )

#             logger.info(
#                 "Password reset token created for user %s",
#                 user.email,
#             )

#             # IMPORTANT:
#             # Do not log reset_token.token in production.
#             # Send the token through your email service instead.

#         return api_response(
#             message=(
#                 "If an account with this email exists, "
#                 "a password reset link has been sent."
#             ),
#         )


# # ============================================================================
# # PASSWORD RESET CONFIRM
# # ============================================================================

# class PasswordResetConfirmView(APIView):
#     """
#     Completes password reset using verified single-use token.
#     """

#     permission_classes = [AllowAny]
#     authentication_classes = []

#     @extend_schema(
#         request=PasswordResetConfirmSerializer,
#         responses={
#             200: MessageResponseSerializer,
#             400: MessageResponseSerializer,
#         },
#         tags=['Authentication'],
#         summary='Confirm password reset',
#         description=(
#             'Set a new password using a valid, single-use password '
#             'reset token.'
#         ),
#     )
#     def post(self, request):

#         serializer = PasswordResetConfirmSerializer(
#             data=request.data,
#         )

#         if not serializer.is_valid():
#             return api_response(
#                 message="Password reset validation failed.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="VALIDATION_ERROR",
#             )

#         token_str = serializer.validated_data['token']

#         new_password = serializer.validated_data['new_password']

#         try:

#             token_obj = PasswordResetToken.objects.get(
#                 token=token_str,
#             )

#             if not token_obj.is_valid:
#                 return api_response(
#                     message=(
#                         "Password reset token has expired "
#                         "or has already been used."
#                     ),
#                     status_code=status.HTTP_400_BAD_REQUEST,
#                     success=False,
#                     code="TOKEN_EXPIRED",
#                 )

#             user = token_obj.user

#             user.set_password(
#                 new_password,
#             )

#             user.save()

#             token_obj.is_used = True

#             token_obj.save()

#             AuditService.log_action(
#                 actor=user,
#                 action="PASSWORD_RESET_COMPLETED",
#                 obj=user,
#                 ip_address=request.META.get('REMOTE_ADDR'),
#             )

#             return api_response(
#                 message=(
#                     "Password reset successfully. "
#                     "You may now sign in with your new password."
#                 ),
#             )

#         except PasswordResetToken.DoesNotExist:

#             return api_response(
#                 message="Invalid password reset token.",
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="INVALID_TOKEN",
#             )


# # ============================================================================
# # EMAIL VERIFICATION
# # ============================================================================

# class VerifyEmailView(APIView):
#     """
#     Verifies user email address using single-use email verification token.
#     """

#     permission_classes = [AllowAny]
#     authentication_classes = []

#     @extend_schema(
#         request=EmailVerificationSerializer,
#         responses={
#             200: MessageResponseSerializer,
#             400: MessageResponseSerializer,
#         },
#         tags=['Authentication'],
#         summary='Verify email',
#         description=(
#             'Verify a user email address using a valid, '
#             'single-use email verification token.'
#         ),
#     )
#     def post(self, request):

#         serializer = EmailVerificationSerializer(
#             data=request.data,
#         )

#         if not serializer.is_valid():
#             return api_response(
#                 message="Token is required.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#             )

#         token_str = serializer.validated_data['token']

#         try:

#             token_obj = EmailVerificationToken.objects.get(
#                 token=token_str,
#             )

#             if not token_obj.is_valid:
#                 return api_response(
#                     message=(
#                         "Email verification token has expired "
#                         "or already used."
#                     ),
#                     status_code=status.HTTP_400_BAD_REQUEST,
#                     success=False,
#                     code="TOKEN_EXPIRED",
#                 )

#             user = token_obj.user

#             user.is_verified = True

#             user.save()

#             token_obj.is_used = True

#             token_obj.save()

#             return api_response(
#                 message="Email verified successfully.",
#             )

#         except EmailVerificationToken.DoesNotExist:

#             return api_response(
#                 message="Invalid verification token.",
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="INVALID_TOKEN",
#             )



 


# import logging
# from django.contrib.auth import get_user_model
# from rest_framework import status
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework.permissions import AllowAny, IsAuthenticated
# from rest_framework_simplejwt.tokens import RefreshToken, TokenError
# from drf_spectacular.utils import extend_schema

# from .serializers import (
#     UserSerializer,
#     UserRegistrationSerializer,
#     UserLoginSerializer,
#     TokenRefreshSerializer,
#     LogoutSerializer,
#     PasswordResetRequestSerializer,
#     PasswordResetConfirmSerializer,
#     EmailVerificationSerializer,
#     MessageResponseSerializer,
# )

# logger = logging.getLogger(__name__)
# User = get_user_model()


# def api_response(message, data=None, status_code=status.HTTP_200_OK, success=True, code=None, errors=None):
#     """
#     Standardized API response helper wrapper.
#     """
#     response_body = {
#         "success": success,
#         "message": message,
#         "data": data,
#         "code": code,
#         "errors": errors,
#     }
#     return Response(response_body, status=status_code)


# # ============================================================================
# # ACCOUNT VIEWS
# # ============================================================================

# class RegisterView(APIView):
#     permission_classes = [AllowAny]
#     serializer_class = UserRegistrationSerializer

#     @extend_schema(
#         summary="Register new user account",
#         tags=['Authentication'],
#         request=UserRegistrationSerializer,
#         responses={201: MessageResponseSerializer, 400: MessageResponseSerializer}
#     )
#     def post(self, request):
#         serializer = UserRegistrationSerializer(data=request.data)
#         if not serializer.is_valid():
#             return api_response("Validation failed.", errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST, success=False)

#         # user = User.objects.create_user(**serializer.validated_data)
#         user = serializer.save()
#         refresh = RefreshToken.for_user(user)

#         return api_response(
#             message="User registered successfully.",
#             data={
#                 "user": UserSerializer(user).data,
#                 "tokens": {
#                     "refresh": str(refresh),
#                     "access": str(refresh.access_token),
#                 }
#             },
#             status_code=status.HTTP_201_CREATED
#         )


# class LoginView(APIView):
#     permission_classes = [AllowAny]
#     serializer_class = UserLoginSerializer

#     @extend_schema(
#         summary="User login",
#         tags=['Authentication'],
#         request=UserLoginSerializer,
#         responses={200: MessageResponseSerializer, 401: MessageResponseSerializer}
#     )
#     def post(self, request):
#         serializer = UserLoginSerializer(data=request.data)
#         if not serializer.is_valid():
#             return api_response("Validation failed.", errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST, success=False)

#         identifier = serializer.validated_data['email']
#         password = serializer.validated_data['password']

#         user = User.objects.filter(email__iexact=identifier).first() or User.objects.filter(username__iexact=identifier).first()

#         if not user or not user.check_password(password):
#             return api_response("Invalid credentials.", status_code=status.HTTP_401_UNAUTHORIZED, success=False)

#         if not user.is_active:
#             return api_response("Account disabled.", status_code=status.HTTP_403_FORBIDDEN, success=False)

#         refresh = RefreshToken.for_user(user)
#         return api_response(
#             message="Login successful.",
#             data={
#                 "user": UserSerializer(user).data,
#                 "tokens": {
#                     "refresh": str(refresh),
#                     "access": str(refresh.access_token),
#                 }
#             }
#         )


# class RefreshTokenView(APIView):
#     permission_classes = [AllowAny]
#     serializer_class = TokenRefreshSerializer

#     @extend_schema(
#         summary="Refresh access token",
#         tags=['Authentication'],
#         request=TokenRefreshSerializer,
#         responses={200: MessageResponseSerializer, 401: MessageResponseSerializer}
#     )
#     def post(self, request):
#         serializer = TokenRefreshSerializer(data=request.data)
#         if not serializer.is_valid():
#             return api_response("Invalid token payload.", errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST, success=False)

#         try:
#             refresh = RefreshToken(serializer.validated_data['refresh'])
#             return api_response(
#                 message="Token refreshed successfully.",
#                 data={"access": str(refresh.access_token)}
#             )
#         except TokenError:
#             return api_response("Token is invalid or expired.", status_code=status.HTTP_401_UNAUTHORIZED, success=False, code="INVALID_TOKEN")


# class LogoutView(APIView):
#     permission_classes = [IsAuthenticated]
#     serializer_class = LogoutSerializer

#     @extend_schema(
#         summary="Logout user and blacklist token",
#         tags=['Authentication'],
#         request=LogoutSerializer,
#         responses={200: MessageResponseSerializer, 400: MessageResponseSerializer}
#     )
#     def post(self, request):
#         serializer = LogoutSerializer(data=request.data)
#         if not serializer.is_valid():
#             return api_response("Refresh token is required.", errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST, success=False)

#         try:
#             token = RefreshToken(serializer.validated_data['refresh'])
#             token.blacklist()
#             return api_response(message="Logged out successfully.")
#         except TokenError:
#             return api_response("Invalid token or token already blacklisted.", status_code=status.HTTP_400_BAD_REQUEST, success=False)


# class CurrentUserView(APIView):
#     permission_classes = [IsAuthenticated]
#     serializer_class = UserSerializer

#     @extend_schema(
#         summary="Get current user profile",
#         tags=['Authentication'],
#         responses={200: UserSerializer, 401: MessageResponseSerializer}
#     )
#     def get(self, request):
#         return api_response(
#             message="Current user fetched successfully.",
#             data=UserSerializer(request.user).data
#         )


# class PasswordResetRequestView(APIView):
#     permission_classes = [AllowAny]
#     serializer_class = PasswordResetRequestSerializer

#     @extend_schema(
#         summary="Request password reset link",
#         tags=['Authentication'],
#         request=PasswordResetRequestSerializer,
#         responses={200: MessageResponseSerializer}
#     )
#     def post(self, request):
#         serializer = PasswordResetRequestSerializer(data=request.data)
#         if not serializer.is_valid():
#             return api_response("Invalid email address.", errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST, success=False)

#         email = serializer.validated_data['email']
#         user = User.objects.filter(email=email, is_active=True).first()

#         if user:
#             logger.info(f"Password reset token requested for {user.email}")

#         return api_response("If an account with this email exists, a reset link has been sent.")


# class PasswordResetConfirmView(APIView):
#     permission_classes = [AllowAny]
#     serializer_class = PasswordResetConfirmSerializer

#     @extend_schema(
#         summary="Confirm password reset",
#         tags=['Authentication'],
#         request=PasswordResetConfirmSerializer,
#         responses={200: MessageResponseSerializer, 400: MessageResponseSerializer}
#     )
#     def post(self, request):
#         serializer = PasswordResetConfirmSerializer(data=request.data)
#         if not serializer.is_valid():
#             return api_response("Validation failed.", errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST, success=False)

#         return api_response("Password reset successfully. You may now sign in.")


# class VerifyEmailView(APIView):
#     permission_classes = [AllowAny]
#     serializer_class = EmailVerificationSerializer

#     @extend_schema(
#         summary="Verify account email",
#         tags=['Authentication'],
#         request=EmailVerificationSerializer,
#         responses={200: MessageResponseSerializer, 400: MessageResponseSerializer}
#     )
#     def post(self, request):
#         serializer = EmailVerificationSerializer(data=request.data)
#         if not serializer.is_valid():
#             return api_response("Token is required.", errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST, success=False)

#         return api_response("Email verified successfully.")



# import logging

# from django.conf import settings
# from django.contrib.auth import get_user_model
# from django.core.mail import send_mail

# from rest_framework import status
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework.permissions import AllowAny, IsAuthenticated

# from rest_framework_simplejwt.tokens import RefreshToken, TokenError

# from drf_spectacular.utils import extend_schema

# from .models import (
#     EmailVerificationToken,
#     EmailVerificationOTP,
#     PasswordResetToken,
# )

# from .serializers import (
#     UserProfileSerializer,
#     UserRegistrationSerializer,
#     UserLoginSerializer,
#     TokenRefreshSerializer,
#     LogoutSerializer,
#     PasswordResetRequestSerializer,
#     PasswordResetConfirmSerializer,
#     EmailVerificationSerializer,
#     SendEmailOTPSerializer,
#     EmailOTPVerificationSerializer,
#     MessageResponseSerializer,
# )


# logger = logging.getLogger(__name__)

# User = get_user_model()


# # ============================================================================
# # STANDARD API RESPONSE
# # ============================================================================

# def api_response(
#     message,
#     data=None,
#     status_code=status.HTTP_200_OK,
#     success=True,
#     code=None,
#     errors=None,
# ):
#     """
#     Standardized API response helper.
#     """

#     response_body = {
#         "success": success,
#         "message": message,
#         "data": data,
#         "code": code,
#         "errors": errors,
#     }

#     return Response(
#         response_body,
#         status=status_code,
#     )


# # ============================================================================
# # HELPER: SEND EMAIL OTP
# # ============================================================================

# def send_email_verification_otp(user, otp):
#     """
#     Sends the verification OTP to the user's email address.
#     """

#     subject = "Your HallBook Email Verification OTP"

#     message = f"""
# Hello {user.full_name},

# Your email verification OTP is:

# {otp}

# This OTP will expire in 10 minutes.

# Do not share this OTP with anyone.

# Regards,
# HallBook Team
# """

#     send_mail(
#         subject=subject,
#         message=message,
#         from_email=settings.DEFAULT_FROM_EMAIL,
#         recipient_list=[user.email],
#         fail_silently=False,
#     )


# # ============================================================================
# # ACCOUNT REGISTRATION
# # ============================================================================

# class RegisterView(APIView):

#     permission_classes = [AllowAny]

#     serializer_class = UserRegistrationSerializer

#     @extend_schema(
#         summary="Register new user account",
#         tags=["Authentication"],
#         request=UserRegistrationSerializer,
#         responses={
#             201: MessageResponseSerializer,
#             400: MessageResponseSerializer,
#         },
#     )
#     def post(self, request):

#         serializer = UserRegistrationSerializer(
#             data=request.data,
#         )

#         if not serializer.is_valid():

#             return api_response(
#                 message="Validation failed.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="VALIDATION_ERROR",
#             )

#         # Create user
#         user = serializer.save()

#         # Generate verification OTP
#         email_otp = EmailVerificationOTP.generate_for_user(
#             user=user,
#             ttl_minutes=10,
#         )

#         # Send OTP email
#         try:

#             send_email_verification_otp(
#                 user=user,
#                 otp=email_otp.otp,
#             )

#         except Exception as exc:

#             logger.exception(
#                 "Failed to send verification OTP to %s",
#                 user.email,
#             )

#             return api_response(
#                 message=(
#                     "User registered successfully, but "
#                     "verification email could not be sent."
#                 ),
#                 data={
#                     "user": UserSerializer(user).data,
#                 },
#                 status_code=status.HTTP_201_CREATED,
#                 success=True,
#                 code="EMAIL_SEND_FAILED",
#             )

#         return api_response(
#             message=(
#                 "User registered successfully. "
#                 "A verification OTP has been sent to your email."
#             ),
#             data={
#                 "user": UserLoginSerializer(user).data,
#             },
#             status_code=status.HTTP_201_CREATED,
#             success=True,
#             code="OTP_SENT",
#         )


# # ============================================================================
# # USER LOGIN
# # ============================================================================

# class LoginView(APIView):

#     permission_classes = [AllowAny]

#     serializer_class = UserLoginSerializer

#     @extend_schema(
#         summary="User login",
#         tags=["Authentication"],
#         request=UserLoginSerializer,
#         responses={
#             200: MessageResponseSerializer,
#             400: MessageResponseSerializer,
#             401: MessageResponseSerializer,
#         },
#     )
#     def post(self, request):

#         serializer = UserLoginSerializer(
#             data=request.data,
#         )

#         if not serializer.is_valid():

#             return api_response(
#                 message="Validation failed.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="VALIDATION_ERROR",
#             )

#         email = serializer.validated_data["email"]
#         password = serializer.validated_data["password"]

#         user = User.objects.filter(
#             email__iexact=email,
#         ).first()

#         if not user or not user.check_password(password):

#             return api_response(
#                 message="Invalid email or password.",
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 success=False,
#                 code="INVALID_CREDENTIALS",
#             )

#         if not user.is_active:

#             return api_response(
#                 message="Your account has been disabled.",
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 success=False,
#                 code="ACCOUNT_DISABLED",
#             )

#         # Optional but recommended:
#         # Do not allow unverified users to login.
#         if not user.is_verified:

#             return api_response(
#                 message=(
#                     "Please verify your email address before logging in."
#                 ),
#                 data={
#                     "email": user.email,
#                     "is_verified": False,
#                 },
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 success=False,
#                 code="EMAIL_NOT_VERIFIED",
#             )

#         refresh = RefreshToken.for_user(
#             user,
#         )

#         return api_response(
#             message="Login successful.",
#             data={
#                 "user": UserLoginSerializer(user).data,
#                 "tokens": {
#                     "refresh": str(refresh),
#                     "access": str(refresh.access_token),
#                 },
#             },
#             success=True,
#             code="LOGIN_SUCCESS",
#         )


# # ============================================================================
# # REFRESH ACCESS TOKEN
# # ============================================================================

# class RefreshTokenView(APIView):

#     permission_classes = [AllowAny]

#     serializer_class = TokenRefreshSerializer

#     @extend_schema(
#         summary="Refresh access token",
#         tags=["Authentication"],
#         request=TokenRefreshSerializer,
#         responses={
#             200: MessageResponseSerializer,
#             401: MessageResponseSerializer,
#         },
#     )
#     def post(self, request):

#         serializer = TokenRefreshSerializer(
#             data=request.data,
#         )

#         if not serializer.is_valid():

#             return api_response(
#                 message="Invalid token payload.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="VALIDATION_ERROR",
#             )

#         try:

#             refresh = RefreshToken(
#                 serializer.validated_data["refresh"],
#             )

#             return api_response(
#                 message="Token refreshed successfully.",
#                 data={
#                     "access": str(
#                         refresh.access_token,
#                     ),
#                 },
#                 success=True,
#                 code="TOKEN_REFRESHED",
#             )

#         except TokenError:

#             return api_response(
#                 message="Token is invalid or expired.",
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 success=False,
#                 code="INVALID_TOKEN",
#             )


# # ============================================================================
# # LOGOUT
# # ============================================================================

# class LogoutView(APIView):

#     permission_classes = [IsAuthenticated]

#     serializer_class = LogoutSerializer

#     @extend_schema(
#         summary="Logout user",
#         tags=["Authentication"],
#         request=LogoutSerializer,
#         responses={
#             200: MessageResponseSerializer,
#             400: MessageResponseSerializer,
#         },
#     )
#     def post(self, request):

#         serializer = LogoutSerializer(
#             data=request.data,
#         )

#         if not serializer.is_valid():

#             return api_response(
#                 message="Refresh token is required.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="VALIDATION_ERROR",
#             )

#         try:

#             token = RefreshToken(
#                 serializer.validated_data["refresh"],
#             )

#             token.blacklist()

#             return api_response(
#                 message="Logged out successfully.",
#                 success=True,
#                 code="LOGOUT_SUCCESS",
#             )

#         except TokenError:

#             return api_response(
#                 message=(
#                     "Invalid token or token has already "
#                     "been blacklisted."
#                 ),
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="INVALID_TOKEN",
#             )


# # ============================================================================
# # CURRENT USER
# # ============================================================================

# class CurrentUserView(APIView):

#     permission_classes = [IsAuthenticated]

#     serializer_class = UserLoginSerializer

#     @extend_schema(
#         summary="Get current user profile",
#         tags=["Authentication"],
#         responses={
#             200: UserLoginSerializer,
#             401: MessageResponseSerializer,
#         },
#     )
#     def get(self, request):

#         return api_response(
#             message="Current user fetched successfully.",
#             data=UserLoginSerializer(
#                 request.user,
#             ).data,
#             success=True,
#         )


# # ============================================================================
# # SEND / RESEND EMAIL VERIFICATION OTP
# # ============================================================================

# class SendEmailOTPView(APIView):

#     permission_classes = [AllowAny]

#     serializer_class = SendEmailOTPSerializer

#     @extend_schema(
#         summary="Send email verification OTP",
#         tags=["Authentication"],
#         request=SendEmailOTPSerializer,
#         responses={
#             200: MessageResponseSerializer,
#             400: MessageResponseSerializer,
#         },
#     )
#     def post(self, request):

#         serializer = SendEmailOTPSerializer(
#             data=request.data,
#         )

#         if not serializer.is_valid():

#             return api_response(
#                 message="Invalid email address.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="VALIDATION_ERROR",
#             )

#         email = serializer.validated_data["email"]

#         user = User.objects.filter(
#             email__iexact=email,
#         ).first()

#         # We do not reveal whether an email exists.
#         if not user:

#             return api_response(
#                 message=(
#                     "If an account with this email exists, "
#                     "a verification OTP has been sent."
#                 ),
#                 success=True,
#             )

#         if user.is_verified:

#             return api_response(
#                 message="This email address is already verified.",
#                 success=True,
#                 code="ALREADY_VERIFIED",
#             )

#         # Generate new OTP
#         email_otp = EmailVerificationOTP.generate_for_user(
#             user=user,
#             ttl_minutes=10,
#         )

#         try:

#             send_email_verification_otp(
#                 user=user,
#                 otp=email_otp.otp,
#             )

#         except Exception:

#             logger.exception(
#                 "Failed to send OTP to %s",
#                 user.email,
#             )

#             return api_response(
#                 message=(
#                     "Unable to send verification OTP. "
#                     "Please try again later."
#                 ),
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                 success=False,
#                 code="EMAIL_SEND_FAILED",
#             )

#         return api_response(
#             message=(
#                 "Verification OTP has been sent to your email."
#             ),
#             data={
#                 "email": user.email,
#                 "expires_in_minutes": 10,
#             },
#             success=True,
#             code="OTP_SENT",
#         )


# # ============================================================================
# # VERIFY EMAIL OTP
# # ============================================================================

# class VerifyEmailOTPView(APIView):

#     permission_classes = [AllowAny]

#     serializer_class = EmailOTPVerificationSerializer

#     MAX_OTP_ATTEMPTS = 5

#     @extend_schema(
#         summary="Verify email using OTP",
#         tags=["Authentication"],
#         request=EmailOTPVerificationSerializer,
#         responses={
#             200: MessageResponseSerializer,
#             400: MessageResponseSerializer,
#         },
#     )
#     def post(self, request):

#         serializer = EmailOTPVerificationSerializer(
#             data=request.data,
#         )

#         if not serializer.is_valid():

#             return api_response(
#                 message="Validation failed.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="VALIDATION_ERROR",
#             )

#         email = serializer.validated_data["email"]
#         submitted_otp = serializer.validated_data["otp"]

#         user = User.objects.filter(
#             email__iexact=email,
#         ).first()

#         if not user:

#             return api_response(
#                 message="Invalid verification request.",
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="INVALID_OTP",
#             )

#         if user.is_verified:

#             return api_response(
#                 message="Email is already verified.",
#                 data={
#                     "user": UserSerializer(user).data,
#                 },
#                 success=True,
#                 code="ALREADY_VERIFIED",
#             )

#         # Get the latest unused OTP
#         email_otp = EmailVerificationOTP.objects.filter(
#             user=user,
#             is_used=False,
#         ).order_by(
#             "-created_at",
#         ).first()

#         if not email_otp:

#             return api_response(
#                 message=(
#                     "No active OTP found. "
#                     "Please request a new OTP."
#                 ),
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="OTP_NOT_FOUND",
#             )

#         # Check expiry
#         if not email_otp.is_valid:

#             email_otp.is_used = True

#             email_otp.save(
#                 update_fields=["is_used"],
#             )

#             return api_response(
#                 message=(
#                     "This OTP has expired. "
#                     "Please request a new OTP."
#                 ),
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="OTP_EXPIRED",
#             )

#         # Check maximum attempts
#         if email_otp.attempts >= self.MAX_OTP_ATTEMPTS:

#             email_otp.is_used = True

#             email_otp.save(
#                 update_fields=["is_used"],
#             )

#             return api_response(
#                 message=(
#                     "Maximum OTP attempts exceeded. "
#                     "Please request a new OTP."
#                 ),
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="MAX_ATTEMPTS_EXCEEDED",
#             )

#         # Increment attempt counter
#         email_otp.attempts += 1

#         # Verify OTP
#         if email_otp.otp != submitted_otp:

#             email_otp.save(
#                 update_fields=["attempts"],
#             )

#             return api_response(
#                 message="Invalid OTP.",
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="INVALID_OTP",
#                 data={
#                     "attempts_remaining": (
#                         self.MAX_OTP_ATTEMPTS
#                         - email_otp.attempts
#                     ),
#                 },
#             )

#         # OTP is correct
#         email_otp.is_used = True

#         email_otp.save(
#             update_fields=[
#                 "attempts",
#                 "is_used",
#             ],
#         )

#         # Mark user as verified
#         user.is_verified = True

#         user.save(
#             update_fields=["is_verified"],
#         )

#         # Generate JWT tokens after successful verification
#         refresh = RefreshToken.for_user(
#             user,
#         )

#         return api_response(
#             message="Email verified successfully.",
#             data={
#                 "user": UserProfSerializer(user).data,
#                 "tokens": {
#                     "refresh": str(refresh),
#                     "access": str(refresh.access_token),
#                 },
#             },
#             success=True,
#             code="EMAIL_VERIFIED",
#         )


# # ============================================================================
# # EMAIL VERIFICATION USING TOKEN
# # EXISTING METHOD - KEPT FOR BACKWARD COMPATIBILITY
# # ============================================================================

# class VerifyEmailView(APIView):

#     permission_classes = [AllowAny]

#     serializer_class = EmailVerificationSerializer

#     @extend_schema(
#         summary="Verify account email using token",
#         tags=["Authentication"],
#         request=EmailVerificationSerializer,
#         responses={
#             200: MessageResponseSerializer,
#             400: MessageResponseSerializer,
#         },
#     )
#     def post(self, request):

#         serializer = EmailVerificationSerializer(
#             data=request.data,
#         )

#         if not serializer.is_valid():

#             return api_response(
#                 message="Token is required.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="VALIDATION_ERROR",
#             )

#         token_value = serializer.validated_data["token"]

#         verification_token = (
#             EmailVerificationToken.objects.filter(
#                 token=token_value,
#                 is_used=False,
#             )
#             .select_related("user")
#             .first()
#         )

#         if not verification_token:

#             return api_response(
#                 message="Invalid verification token.",
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="INVALID_TOKEN",
#             )

#         if not verification_token.is_valid:

#             verification_token.is_used = True

#             verification_token.save(
#                 update_fields=["is_used"],
#             )

#             return api_response(
#                 message=(
#                     "Verification token has expired. "
#                     "Please request a new verification email."
#                 ),
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="TOKEN_EXPIRED",
#             )

#         user = verification_token.user

#         verification_token.is_used = True

#         verification_token.save(
#             update_fields=["is_used"],
#         )

#         user.is_verified = True

#         user.save(
#             update_fields=["is_verified"],
#         )

#         return api_response(
#             message="Email verified successfully.",
#             data={
#                 "user": UserSerializer(user).data,
#             },
#             success=True,
#             code="EMAIL_VERIFIED",
#         )


# # ============================================================================
# # PASSWORD RESET REQUEST
# # ============================================================================

# class PasswordResetRequestView(APIView):

#     permission_classes = [AllowAny]

#     serializer_class = PasswordResetRequestSerializer

#     @extend_schema(
#         summary="Request password reset",
#         tags=["Authentication"],
#         request=PasswordResetRequestSerializer,
#         responses={
#             200: MessageResponseSerializer,
#         },
#     )
#     def post(self, request):

#         serializer = PasswordResetRequestSerializer(
#             data=request.data,
#         )

#         if not serializer.is_valid():

#             return api_response(
#                 message="Invalid email address.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="VALIDATION_ERROR",
#             )

#         email = serializer.validated_data["email"]

#         user = User.objects.filter(
#             email__iexact=email,
#             is_active=True,
#         ).first()

#         if user:

#             # Invalidate previous unused reset tokens
#             PasswordResetToken.objects.filter(
#                 user=user,
#                 is_used=False,
#             ).update(
#                 is_used=True,
#             )

#             reset_token = PasswordResetToken.create_for_user(
#                 user=user,
#                 ttl_hours=2,
#             )

#             logger.info(
#                 "Password reset token created for %s",
#                 user.email,
#             )

#             # You can later send this token as a reset link
#             # using your frontend URL.
#             logger.debug(
#                 "Password reset token: %s",
#                 reset_token.token,
#             )

#         # Always return the same response to prevent
#         # email enumeration.
#         return api_response(
#             message=(
#                 "If an account with this email exists, "
#                 "a password reset link has been sent."
#             ),
#             success=True,
#             code="RESET_REQUEST_ACCEPTED",
#         )


# # ============================================================================
# # PASSWORD RESET CONFIRM
# # ============================================================================

# class PasswordResetConfirmView(APIView):

#     permission_classes = [AllowAny]

#     serializer_class = PasswordResetConfirmSerializer

#     @extend_schema(
#         summary="Confirm password reset",
#         tags=["Authentication"],
#         request=PasswordResetConfirmSerializer,
#         responses={
#             200: MessageResponseSerializer,
#             400: MessageResponseSerializer,
#         },
#     )
#     def post(self, request):

#         serializer = PasswordResetConfirmSerializer(
#             data=request.data,
#         )

#         if not serializer.is_valid():

#             return api_response(
#                 message="Validation failed.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="VALIDATION_ERROR",
#             )

#         token_value = serializer.validated_data["token"]
#         new_password = serializer.validated_data["new_password"]

#         reset_token = (
#             PasswordResetToken.objects.filter(
#                 token=token_value,
#                 is_used=False,
#             )
#             .select_related("user")
#             .first()
#         )

#         if not reset_token:

#             return api_response(
#                 message="Invalid password reset token.",
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="INVALID_TOKEN",
#             )

#         if not reset_token.is_valid:

#             reset_token.is_used = True

#             reset_token.save(
#                 update_fields=["is_used"],
#             )

#             return api_response(
#                 message=(
#                     "Password reset token has expired."
#                 ),
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="TOKEN_EXPIRED",
#             )

#         user = reset_token.user

#         user.set_password(
#             new_password,
#         )

#         user.save(
#             update_fields=["password"],
#         )

#         reset_token.is_used = True

#         reset_token.save(
#             update_fields=["is_used"],
#         )

#         return api_response(
#             message=(
#                 "Password reset successfully. "
#                 "You may now sign in."
#             ),
#             success=True,
#             code="PASSWORD_RESET_SUCCESS",
#         )




import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from drf_spectacular.utils import extend_schema

from .models import (
    EmailVerificationToken,
    EmailVerificationOTP,
    PasswordResetToken,
)

from .serializers import (
    UserProfileSerializer,
    UserRegistrationSerializer,
    UserLoginSerializer,
    TokenRefreshSerializer,
    LogoutSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    EmailVerificationSerializer,
    SendEmailOTPSerializer,
    EmailOTPVerificationSerializer,
    MessageResponseSerializer,
    UserProfileUpdateSerializer,
)


logger = logging.getLogger(__name__)

User = get_user_model()


# ============================================================================
# STANDARD API RESPONSE
# ============================================================================

def api_response(
    message,
    data=None,
    status_code=status.HTTP_200_OK,
    success=True,
    code=None,
    errors=None,
):
    """
    Standardized API response helper.
    """

    response_body = {
        "success": success,
        "message": message,
        "data": data,
        "code": code,
        "errors": errors,
    }

    return Response(
        response_body,
        status=status_code,
    )


# ============================================================================
# HELPER: SEND EMAIL OTP
# ============================================================================

def send_email_verification_otp(user, otp):
    """
    Sends the verification OTP to the user's email address.
    """

    subject = "Your HallBook Email Verification OTP"

    message = f"""
Hello {user.full_name},

Your email verification OTP is:

{otp}

This OTP will expire in 10 minutes.

Do not share this OTP with anyone.

Regards,
HallBook Team
"""

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


# ============================================================================
# ACCOUNT REGISTRATION
# ============================================================================

class RegisterView(APIView):

    permission_classes = [AllowAny]

    serializer_class = UserRegistrationSerializer

    @extend_schema(
        summary="Register new user account",
        tags=["Authentication"],
        request=UserRegistrationSerializer,
        responses={
            201: MessageResponseSerializer,
            400: MessageResponseSerializer,
        },
    )
    def post(self, request):

        serializer = UserRegistrationSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            error_message = "Validation failed."
            flattened = []
            for key, value in serializer.errors.items():
                if isinstance(value, list):
                    flattened.extend(str(item) for item in value)
                elif isinstance(value, dict):
                    for nested_value in value.values():
                        if isinstance(nested_value, list):
                            flattened.extend(str(item) for item in nested_value)
                else:
                    flattened.append(str(value))

            if flattened:
                error_message = flattened[0]

            if "email address already exists" in error_message.lower():
                message = "An account with this email address already exists."
            elif "phone number already exists" in error_message.lower():
                message = "An account with this phone number already exists."
            else:
                message = error_message

            return api_response(
                message=message,
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="VALIDATION_ERROR",
            )

        # Create user with is_verified=False
        user = serializer.save()

        # Generate verification OTP
        email_otp = EmailVerificationOTP.generate_for_user(
            user=user,
            ttl_minutes=10,
        )

        # Send OTP email
        try:

            send_email_verification_otp(
                user=user,
                otp=email_otp.otp,
            )

        except Exception:

            logger.exception(
                "Failed to send verification OTP to %s",
                user.email,
            )

            return api_response(
                message=(
                    "Account created successfully, but the "
                    "verification OTP could not be sent. "
                    "Please use the resend OTP option."
                ),
                data={
                    "user": UserProfileSerializer(user).data,
                    "email": user.email,
                    "role": user.role,
                },
                status_code=status.HTTP_201_CREATED,
                success=True,
                code="EMAIL_SEND_FAILED",
            )

        # IMPORTANT:
        # Do NOT generate JWT tokens here.
        # User must verify OTP before receiving tokens.
        return api_response(
            message=(
                "Account created successfully. "
                "A verification OTP has been sent to your email."
            ),
            data={
                "user": UserProfileSerializer(user).data,
                "email": user.email,
                "role": user.role,
                "is_verified": False,
            },
            status_code=status.HTTP_201_CREATED,
            success=True,
            code="OTP_SENT",
        )


# ============================================================================
# USER LOGIN
# ============================================================================

class LoginView(APIView):

    permission_classes = [AllowAny]

    serializer_class = UserLoginSerializer

    @extend_schema(
        summary="User login",
        tags=["Authentication"],
        request=UserLoginSerializer,
        responses={
            200: MessageResponseSerializer,
            400: MessageResponseSerializer,
            401: MessageResponseSerializer,
        },
    )
    def post(self, request):

        serializer = UserLoginSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            detail_error = None
            for key in ('detail', 'email', 'password'):
                value = serializer.errors.get(key)
                if value:
                    detail_error = value[0] if isinstance(value, list) else str(value)
                    break

            message = detail_error or "Validation failed."
            if "Invalid email address" in message:
                message = "Invalid email address."
            elif "Invalid password" in message:
                message = "Invalid password."
            elif "Invalid email or password" in message:
                message = "Invalid email or password."

            return api_response(
                message=message,
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="VALIDATION_ERROR",
            )

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        user = User.objects.filter(
            email__iexact=email,
        ).first()

        if not user or not user.check_password(password):

            return api_response(
                message="Invalid email or password.",
                status_code=status.HTTP_401_UNAUTHORIZED,
                success=False,
                code="INVALID_CREDENTIALS",
            )

        if not user.is_active:

            return api_response(
                message="Your account has been disabled.",
                status_code=status.HTTP_403_FORBIDDEN,
                success=False,
                code="ACCOUNT_DISABLED",
            )

        # Block login until email OTP is verified
        if not user.is_verified:

            return api_response(
                message=(
                    "Please verify your email address before logging in."
                ),
                data={
                    "email": user.email,
                    "role": user.role,
                    "is_verified": False,
                },
                status_code=status.HTTP_403_FORBIDDEN,
                success=False,
                code="EMAIL_NOT_VERIFIED",
            )

        refresh = RefreshToken.for_user(
            user,
        )

        return api_response(
            message="Login successful.",
            data={
                "user": UserProfileSerializer(user).data,
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            },
            success=True,
            code="LOGIN_SUCCESS",
        )


# ============================================================================
# REFRESH ACCESS TOKEN
# ============================================================================

class RefreshTokenView(APIView):

    permission_classes = [AllowAny]

    serializer_class = TokenRefreshSerializer

    @extend_schema(
        summary="Refresh access token",
        tags=["Authentication"],
        request=TokenRefreshSerializer,
        responses={
            200: MessageResponseSerializer,
            401: MessageResponseSerializer,
        },
    )
    def post(self, request):

        serializer = TokenRefreshSerializer(
            data=request.data,
        )

        if not serializer.is_valid():

            return api_response(
                message="Invalid token payload.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="VALIDATION_ERROR",
            )

        try:

            refresh = RefreshToken(
                serializer.validated_data["refresh"],
            )

            return api_response(
                message="Token refreshed successfully.",
                data={
                    "access": str(
                        refresh.access_token,
                    ),
                },
                success=True,
                code="TOKEN_REFRESHED",
            )

        except TokenError:

            return api_response(
                message="Token is invalid or expired.",
                status_code=status.HTTP_401_UNAUTHORIZED,
                success=False,
                code="INVALID_TOKEN",
            )


# ============================================================================
# LOGOUT
# ============================================================================

class LogoutView(APIView):

    permission_classes = [IsAuthenticated]

    serializer_class = LogoutSerializer

    @extend_schema(
        summary="Logout user",
        tags=["Authentication"],
        request=LogoutSerializer,
        responses={
            200: MessageResponseSerializer,
            400: MessageResponseSerializer,
        },
    )
    def post(self, request):

        serializer = LogoutSerializer(
            data=request.data,
        )

        if not serializer.is_valid():

            return api_response(
                message="Refresh token is required.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="VALIDATION_ERROR",
            )

        try:

            token = RefreshToken(
                serializer.validated_data["refresh"],
            )

            token.blacklist()

            return api_response(
                message="Logged out successfully.",
                success=True,
                code="LOGOUT_SUCCESS",
            )

        except TokenError:

            return api_response(
                message=(
                    "Invalid token or token has already "
                    "been blacklisted."
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="INVALID_TOKEN",
            )


# ============================================================================
# CURRENT USER
# ============================================================================

class CurrentUserView(APIView):

    permission_classes = [IsAuthenticated]

    serializer_class = UserProfileSerializer

    @extend_schema(
        summary="Get current user profile",
        tags=["Authentication"],
        responses={
            200: UserProfileSerializer,
            401: MessageResponseSerializer,
        },
    )
    def get(self, request):

        return api_response(
            message="Current user fetched successfully.",
            data=UserProfileSerializer(
                request.user,
            ).data,
            success=True,
        )

    @extend_schema(
        summary="Update current user profile",
        tags=["Authentication"],
        request=UserProfileUpdateSerializer,
        responses={
            200: UserProfileSerializer,
            400: MessageResponseSerializer,
            401: MessageResponseSerializer,
        },
    )
    def patch(self, request):
        serializer = UserProfileUpdateSerializer(
            instance=request.user,
            data=request.data,
            partial=True,
        )

        if not serializer.is_valid():
            return api_response(
                message="Profile validation failed.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="VALIDATION_ERROR",
            )

        serializer.save()

        return api_response(
            message="Profile updated successfully.",
            data=UserProfileSerializer(request.user).data,
            success=True,
        )


# ============================================================================
# SEND / RESEND EMAIL VERIFICATION OTP
# ============================================================================

class SendEmailOTPView(APIView):

    permission_classes = [AllowAny]

    serializer_class = SendEmailOTPSerializer

    @extend_schema(
        summary="Send email verification OTP",
        tags=["Authentication"],
        request=SendEmailOTPSerializer,
        responses={
            200: MessageResponseSerializer,
            400: MessageResponseSerializer,
        },
    )
    def post(self, request):

        serializer = SendEmailOTPSerializer(
            data=request.data,
        )

        if not serializer.is_valid():

            return api_response(
                message="Invalid email address.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="VALIDATION_ERROR",
            )

        email = serializer.validated_data["email"]

        user = User.objects.filter(
            email__iexact=email,
        ).first()

        # Do not reveal whether an email exists
        if not user:

            return api_response(
                message=(
                    "If an account with this email exists, "
                    "a verification OTP has been sent."
                ),
                success=True,
                code="OTP_REQUEST_ACCEPTED",
            )

        if user.is_verified:

            return api_response(
                message="This email address is already verified.",
                data={
                    "email": user.email,
                    "is_verified": True,
                },
                success=True,
                code="ALREADY_VERIFIED",
            )

        # Generate new OTP
        email_otp = EmailVerificationOTP.generate_for_user(
            user=user,
            ttl_minutes=10,
        )

        try:

            send_email_verification_otp(
                user=user,
                otp=email_otp.otp,
            )

        except Exception:

            logger.exception(
                "Failed to send OTP to %s",
                user.email,
            )

            return api_response(
                message=(
                    "Unable to send verification OTP. "
                    "Please try again later."
                ),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                success=False,
                code="EMAIL_SEND_FAILED",
            )

        return api_response(
            message=(
                "Verification OTP has been sent to your email."
            ),
            data={
                "email": user.email,
                "expires_in_minutes": 10,
            },
            success=True,
            code="OTP_SENT",
        )


# ============================================================================
# VERIFY EMAIL OTP
# ============================================================================

class VerifyEmailOTPView(APIView):

    permission_classes = [AllowAny]

    serializer_class = EmailOTPVerificationSerializer

    MAX_OTP_ATTEMPTS = 5

    @extend_schema(
        summary="Verify email using OTP",
        tags=["Authentication"],
        request=EmailOTPVerificationSerializer,
        responses={
            200: MessageResponseSerializer,
            400: MessageResponseSerializer,
        },
    )
    def post(self, request):

        serializer = EmailOTPVerificationSerializer(
            data=request.data,
        )

        if not serializer.is_valid():

            return api_response(
                message="Validation failed.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="VALIDATION_ERROR",
            )

        email = serializer.validated_data["email"]
        submitted_otp = serializer.validated_data["otp"]

        user = User.objects.filter(
            email__iexact=email,
        ).first()

        if not user:

            return api_response(
                message="Invalid verification request.",
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="INVALID_OTP",
            )

        # If already verified, do not silently create a login session
        if user.is_verified:

            return api_response(
                message=(
                    "This email is already verified. "
                    "Please sign in to continue."
                ),
                data={
                    "email": user.email,
                    "is_verified": True,
                },
                success=True,
                code="ALREADY_VERIFIED",
            )

        # Get latest unused OTP
        email_otp = EmailVerificationOTP.objects.filter(
            user=user,
            is_used=False,
        ).order_by(
            "-created_at",
        ).first()

        if not email_otp:

            return api_response(
                message=(
                    "No active OTP found. "
                    "Please request a new OTP."
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="OTP_NOT_FOUND",
            )

        # Check expiry
        if not email_otp.is_valid:

            email_otp.is_used = True

            email_otp.save(
                update_fields=["is_used"],
            )

            return api_response(
                message=(
                    "This OTP has expired. "
                    "Please request a new OTP."
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="OTP_EXPIRED",
            )

        # Check maximum attempts
        if email_otp.attempts >= self.MAX_OTP_ATTEMPTS:

            email_otp.is_used = True

            email_otp.save(
                update_fields=["is_used"],
            )

            return api_response(
                message=(
                    "Maximum OTP attempts exceeded. "
                    "Please request a new OTP."
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="MAX_ATTEMPTS_EXCEEDED",
            )

        # Increment OTP attempt
        email_otp.attempts += 1

        # Wrong OTP
        if email_otp.otp != submitted_otp:

            email_otp.save(
                update_fields=["attempts"],
            )

            return api_response(
                message="Invalid OTP.",
                data={
                    "attempts_remaining": (
                        self.MAX_OTP_ATTEMPTS
                        - email_otp.attempts
                    ),
                },
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="INVALID_OTP",
            )

        # Correct OTP
        email_otp.is_used = True

        email_otp.save(
            update_fields=[
                "attempts",
                "is_used",
            ],
        )

        # Mark user as verified
        user.is_verified = True

        user.save(
            update_fields=["is_verified"],
        )

        # Generate tokens ONLY after successful OTP verification
        refresh = RefreshToken.for_user(
            user,
        )

        return api_response(
            message="Email verified successfully.",
            data={
                "user": UserProfileSerializer(user).data,
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            },
            success=True,
            code="EMAIL_VERIFIED",
        )


# ============================================================================
# EMAIL VERIFICATION USING TOKEN
# BACKWARD COMPATIBILITY
# ============================================================================

class VerifyEmailView(APIView):

    permission_classes = [AllowAny]

    serializer_class = EmailVerificationSerializer

    @extend_schema(
        summary="Verify account email using token",
        tags=["Authentication"],
        request=EmailVerificationSerializer,
        responses={
            200: MessageResponseSerializer,
            400: MessageResponseSerializer,
        },
    )
    def post(self, request):

        serializer = EmailVerificationSerializer(
            data=request.data,
        )

        if not serializer.is_valid():

            return api_response(
                message="Token is required.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="VALIDATION_ERROR",
            )

        token_value = serializer.validated_data["token"]

        verification_token = (
            EmailVerificationToken.objects.filter(
                token=token_value,
                is_used=False,
            )
            .select_related("user")
            .first()
        )

        if not verification_token:

            return api_response(
                message="Invalid verification token.",
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="INVALID_TOKEN",
            )

        if not verification_token.is_valid:

            verification_token.is_used = True

            verification_token.save(
                update_fields=["is_used"],
            )

            return api_response(
                message=(
                    "Verification token has expired. "
                    "Please request a new verification email."
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="TOKEN_EXPIRED",
            )

        user = verification_token.user

        verification_token.is_used = True

        verification_token.save(
            update_fields=["is_used"],
        )

        user.is_verified = True

        user.save(
            update_fields=["is_verified"],
        )

        return api_response(
            message="Email verified successfully.",
            data={
                "user": UserProfileSerializer(user).data,
            },
            success=True,
            code="EMAIL_VERIFIED",
        )


# ============================================================================
# PASSWORD RESET REQUEST
# ============================================================================

class PasswordResetRequestView(APIView):

    permission_classes = [AllowAny]

    serializer_class = PasswordResetRequestSerializer

    @extend_schema(
        summary="Request password reset",
        tags=["Authentication"],
        request=PasswordResetRequestSerializer,
        responses={
            200: MessageResponseSerializer,
        },
    )
    def post(self, request):

        serializer = PasswordResetRequestSerializer(
            data=request.data,
        )

        if not serializer.is_valid():

            return api_response(
                message="Invalid email address.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="VALIDATION_ERROR",
            )

        email = serializer.validated_data["email"]

        user = User.objects.filter(
            email__iexact=email,
            is_active=True,
        ).first()

        if user:

            PasswordResetToken.objects.filter(
                user=user,
                is_used=False,
            ).update(
                is_used=True,
            )

            reset_token = PasswordResetToken.create_for_user(
                user=user,
                ttl_hours=2,
            )

            logger.info(
                "Password reset token created for %s",
                user.email,
            )

            logger.debug(
                "Password reset token: %s",
                reset_token.token,
            )

        return api_response(
            message=(
                "If an account with this email exists, "
                "a password reset link has been sent."
            ),
            success=True,
            code="RESET_REQUEST_ACCEPTED",
        )


# ============================================================================
# PASSWORD RESET CONFIRM
# ============================================================================

class PasswordResetConfirmView(APIView):

    permission_classes = [AllowAny]

    serializer_class = PasswordResetConfirmSerializer

    @extend_schema(
        summary="Confirm password reset",
        tags=["Authentication"],
        request=PasswordResetConfirmSerializer,
        responses={
            200: MessageResponseSerializer,
            400: MessageResponseSerializer,
        },
    )
    def post(self, request):

        serializer = PasswordResetConfirmSerializer(
            data=request.data,
        )

        if not serializer.is_valid():

            return api_response(
                message="Validation failed.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="VALIDATION_ERROR",
            )

        token_value = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        reset_token = (
            PasswordResetToken.objects.filter(
                token=token_value,
                is_used=False,
            )
            .select_related("user")
            .first()
        )

        if not reset_token:

            return api_response(
                message="Invalid password reset token.",
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="INVALID_TOKEN",
            )

        if not reset_token.is_valid:

            reset_token.is_used = True

            reset_token.save(
                update_fields=["is_used"],
            )

            return api_response(
                message="Password reset token has expired.",
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="TOKEN_EXPIRED",
            )

        user = reset_token.user

        user.set_password(
            new_password,
        )

        user.save(
            update_fields=["password"],
        )

        reset_token.is_used = True

        reset_token.save(
            update_fields=["is_used"],
        )

        return api_response(
            message=(
                "Password reset successfully. "
                "You may now sign in."
            ),
            success=True,
            code="PASSWORD_RESET_SUCCESS",
        )