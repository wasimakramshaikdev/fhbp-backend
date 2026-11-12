from .base import *

DEBUG = False

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test_db.sqlite3',
        'OPTIONS': {
            'timeout': 30,
        },
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
    }
}

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
CELERY_TASK_ALWAYS_EAGER = True

# Payment Gateway in automated test environment defaults to SIMULATED
PAYMENT_GATEWAY_PROVIDER = 'SIMULATED'
RAZORPAY_KEY_ID = 'rzp_test_simulated_key'
RAZORPAY_KEY_SECRET = 'sim_test_secret_1234567890abcdef'
RAZORPAY_WEBHOOK_SECRET = 'sim_webhook_secret_1234567890abcdef'
