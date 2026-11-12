
# import re

# from django.contrib.auth.password_validation import validate_password
# from django.db import transaction

# from rest_framework import serializers
# from drf_spectacular.utils import extend_schema_field

# from apps.accounts.models import (
#     User,
#     UserRole,
#     OwnerProfile,
#     PasswordResetToken,
#     EmailVerificationToken,
#     EmailVerificationOTP,
# )


# # ============================================================================
# # RESPONSE SERIALIZERS
# # ============================================================================

# class MessageResponseSerializer(serializers.Serializer):
#     """
#     Generic API response wrapper.
#     """

#     success = serializers.BooleanField()
#     message = serializers.CharField()
#     code = serializers.CharField(
#         required=False,
#         allow_null=True,
#     )
#     errors = serializers.JSONField(
#         required=False,
#         allow_null=True,
#     )


# class AuthTokensSerializer(serializers.Serializer):
#     access_token = serializers.CharField()
#     refresh_token = serializers.CharField()
#     expires_in = serializers.IntegerField()


# # ============================================================================
# # OWNER PROFILE SERIALIZERS
# # ============================================================================

# class OwnerProfileSerializer(serializers.ModelSerializer):
#     """
#     Serializer for hall owner profile information.

#     The actual bank account number is write-only.
#     A masked version is returned in API responses.
#     """

#     masked_bank_account = serializers.SerializerMethodField()

#     @extend_schema_field(str)
#     def get_masked_bank_account(self, obj):
#         return obj.masked_account_number

#     class Meta:
#         model = OwnerProfile

#         fields = [
#             "id",
#             "business_name",
#             "registration_number",
#             "pan_gst_number",
#             "address",
#             "city",
#             "locality",
#             "bank_account_holder",
#             "bank_account_number",
#             "masked_bank_account",
#             "bank_ifsc_code",
#             "verification_status",
#             "payout_enabled",
#             "created_at",
#             "updated_at",
#         ]

#         extra_kwargs = {
#             "bank_account_number": {
#                 "write_only": True,
#             },
#         }


# # ============================================================================
# # USER SERIALIZERS
# # ============================================================================

# class UserProfileSerializer(serializers.ModelSerializer):
#     """
#     Serializer for authenticated user profile data.
#     """

#     owner_profile = OwnerProfileSerializer(
#         read_only=True,
#     )

#     class Meta:
#         model = User

#         fields = [
#             "id",
#             "email",
#             "phone",
#             "full_name",
#             "role",
#             "is_active",
#             "is_verified",
#             "avatar_url",
#             "owner_profile",
#             "created_at",
#             "updated_at",
#         ]

#         read_only_fields = [
#             "id",
#             "email",
#             "role",
#             "is_active",
#             "is_verified",
#             "created_at",
#             "updated_at",
#         ]


# class AuthResponseDataSerializer(serializers.Serializer):
#     user = UserProfileSerializer()
#     tokens = AuthTokensSerializer()
#     access_token = serializers.CharField()
#     refresh_token = serializers.CharField()
#     expires_in = serializers.IntegerField()


# class AuthResponseSerializer(serializers.Serializer):
#     success = serializers.BooleanField()
#     message = serializers.CharField()
#     data = AuthResponseDataSerializer()


# # ============================================================================
# # USER REGISTRATION
# # ============================================================================

# # class UserRegistrationSerializer(serializers.Serializer):
# #     full_name = serializers.CharField(
# #         max_length=150,
# #         required=True,
# #     )

# #     email = serializers.EmailField(
# #         required=True,
# #     )

# #     phone = serializers.CharField(
# #         max_length=20,
# #         required=False,
# #         allow_blank=True,
# #         allow_null=True,
# #     )

# #     password = serializers.CharField(
# #         write_only=True,
# #         required=True,
# #         min_length=8,
# #     )

# #     confirm_password = serializers.CharField(
# #     write_only=True,
# #     required=True,
# #     min_length=8,
# #     )

# #     role = serializers.ChoiceField(
# #         choices=[
# #             UserRole.CUSTOMER,
# #             UserRole.OWNER,
# #         ],
# #         default=UserRole.CUSTOMER,
# #     )

# #     # Owner-specific fields
# #     business_name = serializers.CharField(
# #         max_length=255,
# #         required=False,
# #         allow_blank=True,
# #     )

# #     registration_number = serializers.CharField(
# #         max_length=100,
# #         required=False,
# #         allow_blank=True,
# #     )

# #     pan_gst_number = serializers.CharField(
# #         max_length=50,
# #         required=False,
# #         allow_blank=True,
# #     )

# #     city = serializers.CharField(
# #         max_length=100,
# #         required=False,
# #         allow_blank=True,
# #         default="Hyderabad",
# #     )

# #     locality = serializers.CharField(
# #         max_length=100,
# #         required=False,
# #         allow_blank=True,
# #     )

# #     def validate_email(self, value):
# #         normalized_email = value.lower().strip()

# #         if User.objects.filter(
# #             email__iexact=normalized_email
# #         ).exists():
# #             raise serializers.ValidationError(
# #                 "An account with this email address already exists."
# #             )

# #         return normalized_email

# #     def validate_phone(self, value):
# #         if value:
# #             clean_phone = re.sub(
# #                 r"[\s\-()]",
# #                 "",
# #                 value,
# #             )

# #             if User.objects.filter(
# #                 phone=clean_phone
# #             ).exists():
# #                 raise serializers.ValidationError(
# #                     "An account with this phone number already exists."
# #                 )

# #             return clean_phone

# #         return None

# #     def validate_password(self, value):
# #         validate_password(value)
# #         return value

# #     def validate(self, attrs):
# #         role = attrs.get("role")
# #         business_name = attrs.get("business_name")

# #         if role == UserRole.OWNER and not business_name:
# #             raise serializers.ValidationError(
# #                 {
# #                     "business_name": [
# #                         "Business name is required for Hall Owner registration."
# #                     ]
# #                 }
# #             )

# #         return attrs

# #     def create(self, validated_data):
# #         role = validated_data["role"]

# #         business_name = validated_data.pop(
# #             "business_name",
# #             "",
# #         )

# #         registration_number = validated_data.pop(
# #             "registration_number",
# #             "",
# #         )

# #         pan_gst_number = validated_data.pop(
# #             "pan_gst_number",
# #             "",
# #         )

# #         city = validated_data.pop(
# #             "city",
# #             "Hyderabad",
# #         )

# #         locality = validated_data.pop(
# #             "locality",
# #             "",
# #         )

# #         with transaction.atomic():

# #             user = User.objects.create_user(
# #                 email=validated_data["email"],
# #                 password=validated_data["password"],
# #                 full_name=validated_data["full_name"],
# #                 phone=validated_data.get("phone"),
# #                 role=role,
# #             )

# #             # New users must verify their email.
# #             user.is_verified = False
# #             user.save(
# #                 update_fields=["is_verified"],
# #             )

# #             # Create owner profile when applicable.
# #             if role == UserRole.OWNER:
# #                 OwnerProfile.objects.create(
# #                     user=user,
# #                     business_name=business_name,
# #                     registration_number=registration_number,
# #                     pan_gst_number=pan_gst_number,
# #                     city=city,
# #                     locality=locality,
# #                 )

# #             # Create a legacy verification token only if your
# #             # existing system still uses it elsewhere.
# #             EmailVerificationToken.create_for_user(user)

# #             # Generate a new 6-digit email verification OTP.
# #             # The view will send this OTP to the user's email.
# #             EmailVerificationOTP.generate_for_user(user)

# #             return user






# class UserRegistrationSerializer(serializers.Serializer):

#     full_name = serializers.CharField(
#         max_length=150,
#         required=True,
#     )

#     email = serializers.EmailField(
#         required=True,
#     )

#     phone = serializers.CharField(
#         max_length=20,
#         required=False,
#         allow_blank=True,
#         allow_null=True,
#     )

#     password = serializers.CharField(
#         write_only=True,
#         required=True,
#         min_length=8,
#     )

#     confirm_password = serializers.CharField(
#         write_only=True,
#         required=True,
#         min_length=8,
#     )

#     role = serializers.ChoiceField(
#         choices=[
#             UserRole.CUSTOMER,
#             UserRole.OWNER,
#         ],
#         default=UserRole.CUSTOMER,
#     )

#     # Owner-specific fields
#     business_name = serializers.CharField(
#         max_length=255,
#         required=False,
#         allow_blank=True,
#     )

#     registration_number = serializers.CharField(
#         max_length=100,
#         required=False,
#         allow_blank=True,
#     )

#     pan_gst_number = serializers.CharField(
#         max_length=50,
#         required=False,
#         allow_blank=True,
#     )

#     city = serializers.CharField(
#         max_length=100,
#         required=False,
#         allow_blank=True,
#         default="Hyderabad",
#     )

#     locality = serializers.CharField(
#         max_length=100,
#         required=False,
#         allow_blank=True,
#     )

#     def validate_email(self, value):
#         normalized_email = value.lower().strip()

#         if User.objects.filter(
#             email__iexact=normalized_email
#         ).exists():
#             raise serializers.ValidationError(
#                 "An account with this email address already exists."
#             )

#         return normalized_email

#     def validate_phone(self, value):
#         if value:
#             clean_phone = re.sub(
#                 r"[\s\-\(\)]",
#                 "",
#                 value,
#             )

#             if User.objects.filter(
#                 phone=clean_phone
#             ).exists():
#                 raise serializers.ValidationError(
#                     "An account with this phone number already exists."
#                 )

#             return clean_phone

#         return None

#     def validate_password(self, value):
#         validate_password(value)
#         return value

#     def validate(self, attrs):
#         password = attrs.get("password")
#         confirm_password = attrs.get("confirm_password")

#         # Validate password confirmation
#         if password != confirm_password:
#             raise serializers.ValidationError(
#                 {
#                     "confirm_password": [
#                         "Passwords do not match."
#                     ]
#                 }
#             )

#         role = attrs.get("role")
#         business_name = attrs.get("business_name")

#         # Business name is required for Hall Owners
#         if role == UserRole.OWNER and not business_name:
#             raise serializers.ValidationError(
#                 {
#                     "business_name": [
#                         "Business name is required for Hall Owner registration."
#                     ]
#                 }
#             )

#         return attrs

#     def create(self, validated_data):

#         # Remove confirm_password because it should never be stored
#         validated_data.pop(
#             "confirm_password",
#             None,
#         )

#         role = validated_data["role"]

#         business_name = validated_data.pop(
#             "business_name",
#             "",
#         )

#         registration_number = validated_data.pop(
#             "registration_number",
#             "",
#         )

#         pan_gst_number = validated_data.pop(
#             "pan_gst_number",
#             "",
#         )

#         city = validated_data.pop(
#             "city",
#             "Hyderabad",
#         )

#         locality = validated_data.pop(
#             "locality",
#             "",
#         )

#         with transaction.atomic():

#             user = User.objects.create_user(
#                 email=validated_data["email"],
#                 password=validated_data["password"],
#                 full_name=validated_data["full_name"],
#                 phone=validated_data.get("phone"),
#                 role=role,
#             )

#             # New users must verify their email
#             user.is_verified = False

#             user.save(
#                 update_fields=["is_verified"],
#             )

#             # Create OwnerProfile for Hall Owners
#             if role == UserRole.OWNER:
#                 OwnerProfile.objects.create(
#                     user=user,
#                     business_name=business_name,
#                     registration_number=registration_number,
#                     pan_gst_number=pan_gst_number,
#                     city=city,
#                     locality=locality,
#                 )

#             # Legacy email verification token
#             EmailVerificationToken.create_for_user(
#                 user
#             )

#             # Generate 6-digit OTP for email verification
#             EmailVerificationOTP.generate_for_user(
#                 user
#             )

#             return user



# # ============================================================================
# # USER LOGIN
# # ============================================================================

# class UserLoginSerializer(serializers.Serializer):
#     email = serializers.EmailField(
#         required=True,
#     )

#     password = serializers.CharField(
#         write_only=True,
#         required=True,
#     )

#     def validate(self, attrs):
#         email = attrs.get(
#             "email",
#             "",
#         ).lower().strip()

#         password = attrs.get("password")

#         try:
#             user = User.objects.get(
#                 email__iexact=email,
#             )
#         except User.DoesNotExist:
#             raise serializers.ValidationError(
#                 {
#                     "detail": "Invalid email or password."
#                 }
#             )

#         if not user.check_password(password):
#             raise serializers.ValidationError(
#                 {
#                     "detail": "Invalid email or password."
#                 }
#             )

#         if not user.is_active:
#             raise serializers.ValidationError(
#                 {
#                     "detail": (
#                         "Your account has been deactivated. "
#                         "Please contact support."
#                     )
#                 }
#             )

#         # Super Admins should not be blocked if they are already
#         # verified. Other users must verify their email.
#         if not user.is_verified:
#             raise serializers.ValidationError(
#                 {
#                     "detail": (
#                         "Please verify your email address before logging in."
#                     ),
#                     "email": user.email,
#                     "verification_required": True,
#                 }
#             )

#         attrs["user"] = user

#         return attrs


# # ============================================================================
# # EMAIL OTP VERIFICATION
# # ============================================================================

# class EmailOTPVerificationSerializer(serializers.Serializer):
#     """
#     Used when the user enters the 6-digit OTP.
#     """

#     email = serializers.EmailField(
#         required=True,
#     )

#     otp = serializers.CharField(
#         required=True,
#         min_length=6,
#         max_length=6,
#     )

#     def validate_email(self, value):
#         return value.lower().strip()

#     def validate_otp(self, value):
#         otp = value.strip()

#         if not otp.isdigit():
#             raise serializers.ValidationError(
#                 "OTP must contain exactly 6 digits."
#             )

#         return otp


# class SendEmailOTPSerializer(serializers.Serializer):
#     """
#     Used to request a new email verification OTP.
#     """

#     email = serializers.EmailField(
#         required=True,
#     )

#     def validate_email(self, value):
#         email = value.lower().strip()

#         try:
#             user = User.objects.get(
#                 email__iexact=email,
#             )
#         except User.DoesNotExist:
#             raise serializers.ValidationError(
#                 "No account exists with this email address."
#             )

#         if user.is_verified:
#             raise serializers.ValidationError(
#                 "This email address is already verified."
#             )

#         return email


# # ============================================================================
# # USER PROFILE UPDATE
# # ============================================================================

# class UserProfileUpdateSerializer(serializers.Serializer):
#     full_name = serializers.CharField(
#         max_length=150,
#         required=False,
#     )

#     phone = serializers.CharField(
#         max_length=20,
#         required=False,
#         allow_blank=True,
#         allow_null=True,
#     )

#     avatar_url = serializers.URLField(
#         max_length=500,
#         required=False,
#         allow_blank=True,
#     )

#     # Owner-specific fields
#     business_name = serializers.CharField(
#         max_length=255,
#         required=False,
#     )

#     registration_number = serializers.CharField(
#         max_length=100,
#         required=False,
#         allow_blank=True,
#     )

#     pan_gst_number = serializers.CharField(
#         max_length=50,
#         required=False,
#         allow_blank=True,
#     )

#     address = serializers.CharField(
#         max_length=255,
#         required=False,
#         allow_blank=True,
#     )

#     city = serializers.CharField(
#         max_length=100,
#         required=False,
#     )

#     locality = serializers.CharField(
#         max_length=100,
#         required=False,
#         allow_blank=True,
#     )

#     bank_account_holder = serializers.CharField(
#         max_length=150,
#         required=False,
#         allow_blank=True,
#     )

#     bank_account_number = serializers.CharField(
#         max_length=50,
#         required=False,
#         allow_blank=True,
#     )

#     bank_ifsc_code = serializers.CharField(
#         max_length=20,
#         required=False,
#         allow_blank=True,
#     )

#     def update(self, instance, validated_data):

#         with transaction.atomic():

#             if "full_name" in validated_data:
#                 instance.full_name = validated_data[
#                     "full_name"
#                 ]

#             if "phone" in validated_data:
#                 new_phone = validated_data[
#                     "phone"
#                 ]

#                 if new_phone:
#                     clean_phone = re.sub(
#                         r"[\s\-()]",
#                         "",
#                         new_phone,
#                     )

#                     phone_exists = User.objects.filter(
#                         phone=clean_phone,
#                     ).exclude(
#                         id=instance.id,
#                     ).exists()

#                     if phone_exists:
#                         raise serializers.ValidationError(
#                             {
#                                 "phone": [
#                                     "Phone number already in use by another user."
#                                 ]
#                             }
#                         )

#                     instance.phone = clean_phone

#                 else:
#                     instance.phone = None

#             if "avatar_url" in validated_data:
#                 instance.avatar_url = validated_data[
#                     "avatar_url"
#                 ]

#             instance.save()

#             # Update owner profile if applicable.
#             if (
#                 instance.is_owner
#                 and hasattr(instance, "owner_profile")
#             ):
#                 profile = instance.owner_profile

#                 owner_fields = [
#                     "business_name",
#                     "registration_number",
#                     "pan_gst_number",
#                     "address",
#                     "city",
#                     "locality",
#                     "bank_account_holder",
#                     "bank_account_number",
#                     "bank_ifsc_code",
#                 ]

#                 for field in owner_fields:
#                     if field in validated_data:
#                         setattr(
#                             profile,
#                             field,
#                             validated_data[field],
#                         )

#                 profile.save()

#             return instance


# # ============================================================================
# # PASSWORD RESET
# # ============================================================================

# class PasswordResetRequestSerializer(serializers.Serializer):
#     email = serializers.EmailField(
#         required=True,
#     )

#     def validate_email(self, value):
#         return value.lower().strip()


# # class PasswordResetConfirmSerializer(serializers.Serializer):
# #     token = serializers.CharField(
# #         required=True,
# #     )

# #     new_password = serializers.CharField(
# #         write_only=True,
# #         required=True,
# #         min_length=8,
# #     )

# #     def validate_new_password(self, value):
# #         validate_password(value)
# #         return value


# # ============================================================================
# # LEGACY EMAIL TOKEN VERIFICATION
# # ============================================================================

# class EmailVerificationSerializer(serializers.Serializer):
#     """
#     Kept for compatibility with your existing token-based
#     email verification endpoint.
#     """

#     token = serializers.CharField(
#         required=True,
#     )


# # ============================================================================
# # JWT SERIALIZERS
# # ============================================================================

# class TokenRefreshSerializer(serializers.Serializer):
#     refresh = serializers.CharField(
#         help_text="Valid JWT refresh token string."
#     )


# class LogoutSerializer(serializers.Serializer):
#     refresh = serializers.CharField(
#         help_text="JWT refresh token to blacklist."
#     )


# class PasswordResetConfirmSerializer(serializers.Serializer):
#     token = serializers.CharField(
#         required=True,
#     )

#     new_password = serializers.CharField(
#         required=True,
#         write_only=True,
#         min_length=8,
#     )

#     confirm_password = serializers.CharField(
#         required=True,
#         write_only=True,
#         min_length=8,
#     )

#     def validate(self, attrs):
#         if attrs["new_password"] != attrs["confirm_password"]:
#             raise serializers.ValidationError(
#                 {
#                     "confirm_password": [
#                         "Passwords do not match."
#                     ]
#                 }
#             )

#         return attrs





import re

from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from rest_framework import serializers

from drf_spectacular.utils import extend_schema_field

from apps.accounts.models import (
    User,
    UserRole,
    OwnerProfile,
)


# ============================================================================
# RESPONSE SERIALIZERS
# ============================================================================

class MessageResponseSerializer(serializers.Serializer):
    """
    Generic standardized API response wrapper.
    """

    success = serializers.BooleanField()
    message = serializers.CharField()

    data = serializers.JSONField(
        required=False,
        allow_null=True,
    )

    code = serializers.CharField(
        required=False,
        allow_null=True,
    )

    errors = serializers.JSONField(
        required=False,
        allow_null=True,
    )


class AuthTokensSerializer(serializers.Serializer):
    """
    JWT token response serializer.
    """

    access = serializers.CharField()
    refresh = serializers.CharField()


# ============================================================================
# OWNER PROFILE SERIALIZER
# ============================================================================

class OwnerProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for hall owner profile information.

    The actual bank account number is write-only.
    A masked version is returned in API responses.
    """

    masked_bank_account = serializers.SerializerMethodField()

    @extend_schema_field(str)
    def get_masked_bank_account(self, obj):
        return obj.masked_account_number

    class Meta:
        model = OwnerProfile

        fields = [
            "id",
            "business_name",
            "registration_number",
            "pan_gst_number",
            "address",
            "city",
            "locality",
            "bank_account_holder",
            "bank_account_number",
            "masked_bank_account",
            "bank_ifsc_code",
            "id_proof",
            "business_proof",
            "verification_status",
            "payout_enabled",
            "notes",
            "verification_notes",
            "created_at",
            "updated_at",
        ]

        extra_kwargs = {
            "bank_account_number": {
                "write_only": True,
            },
        }


# ============================================================================
# USER PROFILE SERIALIZER
# ============================================================================

class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for authenticated user profile data.
    """

    owner_profile = serializers.SerializerMethodField()

    def get_owner_profile(self, obj):
        try:
            profile = obj.owner_profile
        except OwnerProfile.DoesNotExist:
            return None
        return OwnerProfileSerializer(profile, read_only=True).data

    class Meta:
        model = User

        fields = [
            "id",
            "email",
            "phone",
            "full_name",
            "role",
            "is_active",
            "is_verified",
            "avatar_url",
            "owner_profile",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "email",
            "role",
            "is_active",
            "is_verified",
            "created_at",
            "updated_at",
        ]


# ============================================================================
# USER REGISTRATION SERIALIZER
# ============================================================================

class UserRegistrationSerializer(serializers.Serializer):

    full_name = serializers.CharField(
        max_length=150,
        required=True,
    )

    email = serializers.EmailField(
        required=True,
    )

    phone = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8,
    )

    confirm_password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8,
    )

    role = serializers.ChoiceField(
        choices=[
            UserRole.CUSTOMER,
            UserRole.OWNER,
        ],
        default=UserRole.CUSTOMER,
    )

    # Owner-specific fields

    business_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
    )

    registration_number = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )

    pan_gst_number = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
    )

    city = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        default="Hyderabad",
    )

    locality = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )

    # ------------------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------------------

    def validate_email(self, value):

        email = value.lower().strip()

        if User.objects.filter(
            email__iexact=email,
        ).exists():

            raise serializers.ValidationError(
                "An account with this email address already exists."
            )

        return email

    def validate_phone(self, value):

        if not value:
            return None

        clean_phone = re.sub(
            r"[\s\-()]",
            "",
            value,
        )

        if User.objects.filter(
            phone=clean_phone,
        ).exists():

            raise serializers.ValidationError(
                "An account with this phone number already exists."
            )

        return clean_phone

    def validate_password(self, value):

        validate_password(value)

        return value

    def validate(self, attrs):

        password = attrs.get("password")
        confirm_password = attrs.get("confirm_password")

        if password != confirm_password:

            raise serializers.ValidationError(
                {
                    "confirm_password": [
                        "Passwords do not match."
                    ]
                }
            )

        role = attrs.get("role")
        business_name = attrs.get("business_name")

        if (
            role == UserRole.OWNER
            and not business_name
        ):

            raise serializers.ValidationError(
                {
                    "business_name": [
                        "Business name is required for Hall Owner registration."
                    ]
                }
            )

        return attrs

    # ------------------------------------------------------------------------
    # CREATE USER
    # ------------------------------------------------------------------------

    def create(self, validated_data):

        validated_data.pop(
            "confirm_password",
            None,
        )

        role = validated_data.get(
            "role",
            UserRole.CUSTOMER,
        )

        business_name = validated_data.pop(
            "business_name",
            "",
        )

        registration_number = validated_data.pop(
            "registration_number",
            "",
        )

        pan_gst_number = validated_data.pop(
            "pan_gst_number",
            "",
        )

        city = validated_data.pop(
            "city",
            "Hyderabad",
        )

        locality = validated_data.pop(
            "locality",
            "",
        )

        with transaction.atomic():

            user = User.objects.create_user(
                email=validated_data["email"],
                password=validated_data["password"],
                full_name=validated_data["full_name"],
                phone=validated_data.get("phone"),
                role=role,
            )

            # New users must verify their email
            user.is_verified = False

            user.save(
                update_fields=[
                    "is_verified",
                ],
            )

            # Create owner profile for owners
            if role == UserRole.OWNER:

                OwnerProfile.objects.create(
                    user=user,
                    business_name=business_name,
                    registration_number=registration_number,
                    pan_gst_number=pan_gst_number,
                    city=city,
                    locality=locality,
                )

            return user


# ============================================================================
# USER LOGIN SERIALIZER
# ============================================================================

class UserLoginSerializer(serializers.Serializer):

    email = serializers.EmailField(
        required=True,
    )

    password = serializers.CharField(
        write_only=True,
        required=True,
    )

    def validate_email(self, value):

        return value.lower().strip()

    def validate(self, attrs):

        email = attrs.get("email")
        password = attrs.get("password")

        user = User.objects.filter(
            email__iexact=email,
        ).first()

        if not user:
            raise serializers.ValidationError(
                {
                    "detail": "Invalid email address."
                }
            )

        if not user.check_password(password):
            raise serializers.ValidationError(
                {
                    "detail": "Invalid password."
                }
            )

        if not user.is_active:

            raise serializers.ValidationError(
                {
                    "detail": (
                        "Your account has been deactivated. "
                        "Please contact support."
                    )
                }
            )

        if not user.is_verified:

            raise serializers.ValidationError(
                {
                    "detail": (
                        "Please verify your email address before logging in."
                    ),
                    "email": user.email,
                    "verification_required": True,
                }
            )

        attrs["user"] = user

        return attrs


# ============================================================================
# EMAIL OTP VERIFICATION SERIALIZER
# ============================================================================

class EmailOTPVerificationSerializer(serializers.Serializer):
    """
    Used when the user enters the 6-digit email verification OTP.
    """

    email = serializers.EmailField(
        required=True,
    )

    otp = serializers.CharField(
        required=True,
        min_length=6,
        max_length=6,
    )

    def validate_email(self, value):

        return value.lower().strip()

    def validate_otp(self, value):

        otp = value.strip()

        if not otp.isdigit():

            raise serializers.ValidationError(
                "OTP must contain exactly 6 digits."
            )

        if len(otp) != 6:

            raise serializers.ValidationError(
                "OTP must contain exactly 6 digits."
            )

        return otp


# ============================================================================
# SEND / RESEND EMAIL OTP SERIALIZER
# ============================================================================

class SendEmailOTPSerializer(serializers.Serializer):
    """
    Used to request a new email verification OTP.
    """

    email = serializers.EmailField(
        required=True,
    )

    def validate_email(self, value):

        return value.lower().strip()


# ============================================================================
# LEGACY EMAIL TOKEN VERIFICATION SERIALIZER
# ============================================================================

class EmailVerificationSerializer(serializers.Serializer):
    """
    Kept for compatibility with the token-based email verification endpoint.
    """

    token = serializers.CharField(
        required=True,
    )


# ============================================================================
# TOKEN REFRESH SERIALIZER
# ============================================================================

class TokenRefreshSerializer(serializers.Serializer):

    refresh = serializers.CharField(
        required=True,
        help_text="Valid JWT refresh token string.",
    )


# ============================================================================
# LOGOUT SERIALIZER
# ============================================================================

class LogoutSerializer(serializers.Serializer):

    refresh = serializers.CharField(
        required=True,
        help_text="JWT refresh token to blacklist.",
    )


# ============================================================================
# USER PROFILE UPDATE SERIALIZER
# ============================================================================

class UserProfileUpdateSerializer(serializers.Serializer):

    full_name = serializers.CharField(
        max_length=150,
        required=False,
    )

    phone = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    avatar_url = serializers.URLField(
        max_length=500,
        required=False,
        allow_blank=True,
    )

    # Owner-specific fields

    business_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
    )

    registration_number = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )

    pan_gst_number = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
    )

    address = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
    )

    city = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )

    locality = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )

    bank_account_holder = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
    )

    bank_account_number = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
    )

    bank_ifsc_code = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
    )

    id_proof = serializers.FileField(
        required=False,
        allow_null=True,
    )

    business_proof = serializers.FileField(
        required=False,
        allow_null=True,
    )

    verification_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    def update(self, instance, validated_data):

        with transaction.atomic():

            if "full_name" in validated_data:

                instance.full_name = validated_data[
                    "full_name"
                ]

            if "phone" in validated_data:

                new_phone = validated_data[
                    "phone"
                ]

                if new_phone:

                    clean_phone = re.sub(
                        r"[\s\-()]",
                        "",
                        new_phone,
                    )

                    phone_exists = (
                        User.objects.filter(
                            phone=clean_phone,
                        )
                        .exclude(
                            id=instance.id,
                        )
                        .exists()
                    )

                    if phone_exists:

                        raise serializers.ValidationError(
                            {
                                "phone": [
                                    "Phone number already in use by another user."
                                ]
                            }
                        )

                    instance.phone = clean_phone

                else:

                    instance.phone = None

            if "avatar_url" in validated_data:

                instance.avatar_url = validated_data[
                    "avatar_url"
                ]

            instance.save()

            # Update owner profile
            if (
                instance.is_owner
                and hasattr(
                    instance,
                    "owner_profile",
                )
            ):

                profile = instance.owner_profile

                owner_fields = [
                    "business_name",
                    "registration_number",
                    "pan_gst_number",
                    "address",
                    "city",
                    "locality",
                    "bank_account_holder",
                    "bank_account_number",
                    "bank_ifsc_code",
                    "verification_notes",
                ]

                for field in owner_fields:

                    if field in validated_data:

                        setattr(
                            profile,
                            field,
                            validated_data[field],
                        )

                if "id_proof" in validated_data:
                    profile.id_proof = validated_data["id_proof"]
                if "business_proof" in validated_data:
                    profile.business_proof = validated_data["business_proof"]

                profile.save()

            return instance


# ============================================================================
# PASSWORD RESET REQUEST SERIALIZER
# ============================================================================

class PasswordResetRequestSerializer(serializers.Serializer):

    email = serializers.EmailField(
        required=True,
    )

    def validate_email(self, value):

        return value.lower().strip()


# ============================================================================
# PASSWORD RESET CONFIRM SERIALIZER
# ============================================================================

class PasswordResetConfirmSerializer(serializers.Serializer):

    token = serializers.CharField(
        required=True,
    )

    new_password = serializers.CharField(
        required=True,
        write_only=True,
        min_length=8,
    )

    confirm_password = serializers.CharField(
        required=True,
        write_only=True,
        min_length=8,
    )

    def validate_new_password(self, value):

        validate_password(value)

        return value

    def validate(self, attrs):

        if (
            attrs.get("new_password")
            != attrs.get("confirm_password")
        ):

            raise serializers.ValidationError(
                {
                    "confirm_password": [
                        "Passwords do not match."
                    ]
                }
            )

        return attrs