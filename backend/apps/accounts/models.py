import uuid
import secrets
from datetime import datetime, timedelta, timezone
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from apps.core.models import TimeStampedModel, UUIDModel

class UserRole(models.TextChoices):
    CUSTOMER = 'CUSTOMER', 'Customer'
    OWNER = 'OWNER', 'Hall Owner'
    ADMIN = 'ADMIN', 'Super Admin'


class OwnerVerificationStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Verification'
    VERIFIED = 'VERIFIED', 'Verified'
    REJECTED = 'REJECTED', 'Rejected'
    SUSPENDED = 'SUSPENDED', 'Suspended'


class UserManager(BaseUserManager):
    """Custom user manager supporting email-based authentication."""
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email address must be provided')
        email = self.normalize_email(email).lower()
        extra_fields.setdefault('is_active', True)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', UserRole.ADMIN)
        extra_fields.setdefault('is_verified', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, UUIDModel, TimeStampedModel):
    """
    Authoritative Custom User Model for HallBook.
    Email is the unique identifier for authentication.
    """
    email = models.EmailField(unique=True, db_index=True, max_length=255)
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True, db_index=True)
    full_name = models.CharField(max_length=150)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CUSTOMER,
        db_index=True
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    avatar_url = models.URLField(max_length=500, blank=True, default="")

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'role']),
            models.Index(fields=['role', 'is_active']),
        ]

    def __str__(self):
        return f"{self.full_name} <{self.email}> ({self.role})"

    @property
    def is_customer(self):
        return self.role == UserRole.CUSTOMER

    @property
    def is_owner(self):
        return self.role == UserRole.OWNER

    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN or self.is_superuser


class OwnerProfile(UUIDModel, TimeStampedModel):
    """
    Extended business and financial profile for Hall Owners.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='owner_profile'
    )
    business_name = models.CharField(max_length=255)
    registration_number = models.CharField(max_length=100, blank=True, default="")
    pan_gst_number = models.CharField(max_length=50, blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100, default="Hyderabad")
    locality = models.CharField(max_length=100, blank=True, default="")
    bank_account_holder = models.CharField(max_length=150, blank=True, default="")
    bank_account_number = models.CharField(max_length=50, blank=True, default="")
    bank_ifsc_code = models.CharField(max_length=20, blank=True, default="")
    id_proof = models.FileField(upload_to='owner_kyc/id_proof/%Y/%m/%d/', blank=True, null=True)
    business_proof = models.FileField(upload_to='owner_kyc/business_proof/%Y/%m/%d/', blank=True, null=True)
    verification_status = models.CharField(
        max_length=20,
        choices=OwnerVerificationStatus.choices,
        default=OwnerVerificationStatus.PENDING,
        db_index=True
    )
    payout_enabled = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default="")
    verification_notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = 'owner_profiles'
        verbose_name = 'Owner Profile'
        verbose_name_plural = 'Owner Profiles'

    def __str__(self):
        return f"{self.business_name} ({self.user.email})"

    @property
    def masked_account_number(self):
        if self.bank_account_number and len(self.bank_account_number) > 4:
            return f"**** **** {self.bank_account_number[-4:]}"
        return "****"


class PasswordResetToken(UUIDModel, TimeStampedModel):
    """Secure single-use token for password recovery."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_tokens')
    token = models.CharField(max_length=128, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = 'password_reset_tokens'
        ordering = ['-created_at']

    @classmethod
    def create_for_user(cls, user, ttl_hours=2):
        token = secrets.token_urlsafe(48)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        return cls.objects.create(user=user, token=token, expires_at=expires_at)

    @property
    def is_valid(self):
        return not self.is_used and self.expires_at > datetime.now(timezone.utc)


class EmailVerificationToken(UUIDModel, TimeStampedModel):
    """Token for validating user email authenticity."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_verification_tokens')
    token = models.CharField(max_length=128, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = 'email_verification_tokens'
        ordering = ['-created_at']

    @classmethod
    def create_for_user(cls, user, ttl_days=3):
        token = secrets.token_urlsafe(48)
        expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)
        return cls.objects.create(user=user, token=token, expires_at=expires_at)

    @property
    def is_valid(self):
        return not self.is_used and self.expires_at > datetime.now(timezone.utc)


class EmailVerificationOTP(UUIDModel, TimeStampedModel):
    """
    Stores a short-lived OTP used to verify a user's email address.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="email_verification_otps",
    )

    otp = models.CharField(
        max_length=6,
        db_index=True,
    )

    expires_at = models.DateTimeField(
        db_index=True,
    )

    is_used = models.BooleanField(
        default=False,
    )

    attempts = models.PositiveIntegerField(
        default=0,
    )

    class Meta:
        db_table = "email_verification_otps"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "is_used", "expires_at"]
            ),
        ]

    @classmethod
    def generate_for_user(cls, user, ttl_minutes=10):
        """
        Invalidates previous unused OTPs and creates a new 6-digit OTP.
        """

        cls.objects.filter(
            user=user,
            is_used=False,
        ).update(
            is_used=True,
        )

        otp = f"{secrets.randbelow(1000000):06d}"

        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(minutes=ttl_minutes)
        )

        return cls.objects.create(
            user=user,
            otp=otp,
            expires_at=expires_at,
        )

    @property
    def is_valid(self):
        return (
            not self.is_used
            and self.expires_at > datetime.now(timezone.utc)
        )


class RevokedRefreshToken(UUIDModel, TimeStampedModel):
    """Blacklist table for invalidated refresh tokens upon logout or password change."""
    token_jti = models.CharField(max_length=128, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='revoked_tokens')
    revoked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'revoked_refresh_tokens'
