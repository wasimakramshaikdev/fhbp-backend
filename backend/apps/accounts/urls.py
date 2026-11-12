# from django.urls import path
# from apps.accounts.views import (
#     RegisterView,
#     LoginView,
#     RefreshTokenView,
#     LogoutView,
#     CurrentUserView,
#     PasswordResetRequestView,
#     PasswordResetConfirmView,
#     VerifyEmailView
# )

# urlpatterns = [
#     path('register/', RegisterView.as_view(), name='auth-register'),
#     path('login/', LoginView.as_view(), name='auth-login'),
#     path('refresh/', RefreshTokenView.as_view(), name='auth-refresh'),
#     path('logout/', LogoutView.as_view(), name='auth-logout'),
#     path('me/', CurrentUserView.as_view(), name='auth-me'),
#     path('password-reset/', PasswordResetRequestView.as_view(), name='auth-password-reset-request'),
#     path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='auth-password-reset-confirm'),
#     path('verify-email/', VerifyEmailView.as_view(), name='auth-verify-email'),
# ]



# from django.urls import path

# from apps.accounts.views import (
#     RegisterView,
#     LoginView,
#     RefreshTokenView,
#     LogoutView,
#     CurrentUserView,
#     PasswordResetRequestView,
#     PasswordResetConfirmView,
#     VerifyEmailView,
#     SendEmailOTPView,
#     VerifyEmailOTPView,
# )


# urlpatterns = [
#     # Authentication
#     path(
#         'register/',
#         RegisterView.as_view(),
#         name='auth-register',
#     ),

#     path(
#         'login/',
#         LoginView.as_view(),
#         name='auth-login',
#     ),

#     path(
#         'refresh/',
#         RefreshTokenView.as_view(),
#         name='auth-refresh',
#     ),

#     path(
#         'logout/',
#         LogoutView.as_view(),
#         name='auth-logout',
#     ),

#     path(
#         'me/',
#         CurrentUserView.as_view(),
#         name='auth-me',
#     ),

#     # Password Reset
#     path(
#         'password-reset/',
#         PasswordResetRequestView.as_view(),
#         name='auth-password-reset-request',
#     ),

#     path(
#         'password-reset/confirm/',
#         PasswordResetConfirmView.as_view(),
#         name='auth-password-reset-confirm',
#     ),

#     # Legacy Email Verification
#     path(
#         'verify-email/',
#         VerifyEmailView.as_view(),
#         name='auth-verify-email',
#     ),

#     # Send / Resend Email OTP
#     path(
#         'send-email-otp/',
#         SendEmailOTPView.as_view(),
#         name='auth-send-email-otp',
#     ),

#     # Verify Email OTP
#     path(
#         'verify-email-otp/',
#         VerifyEmailOTPView.as_view(),
#         name='auth-verify-email-otp',
#     ),
# ]



from django.urls import path

from apps.accounts.views import (
    RegisterView,
    LoginView,
    RefreshTokenView,
    LogoutView,
    CurrentUserView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    VerifyEmailView,
    SendEmailOTPView,
    VerifyEmailOTPView,
)


urlpatterns = [
    # Authentication
    path(
        'register/',
        RegisterView.as_view(),
        name='auth-register',
    ),

    path(
        'login/',
        LoginView.as_view(),
        name='auth-login',
    ),

    path(
        'refresh/',
        RefreshTokenView.as_view(),
        name='auth-refresh',
    ),

    path(
        'logout/',
        LogoutView.as_view(),
        name='auth-logout',
    ),

    path(
        'me/',
        CurrentUserView.as_view(),
        name='auth-me',
    ),

    # Password Reset
    path(
        'password-reset/',
        PasswordResetRequestView.as_view(),
        name='auth-password-reset-request',
    ),

    path(
        'password-reset/confirm/',
        PasswordResetConfirmView.as_view(),
        name='auth-password-reset-confirm',
    ),

    # Legacy token-based email verification
    path(
        'verify-email/',
        VerifyEmailView.as_view(),
        name='auth-verify-email',
    ),

    # Send / Resend Email OTP
    path(
        'send-email-otp/',
        SendEmailOTPView.as_view(),
        name='auth-send-email-otp',
    ),

    # Verify Email OTP
    path(
        'verify-email-otp/',
        VerifyEmailOTPView.as_view(),
        name='auth-verify-email-otp',
    ),
]