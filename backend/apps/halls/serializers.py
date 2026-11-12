from urllib.parse import urlparse

from rest_framework import serializers

from apps.halls.models import (
    Hall,
    HallImage,
    Amenity,
    HallApprovalStatus,
    HallStatus,
)


# ---------------------------------------------------------------------------
# Image URL Validation
# ---------------------------------------------------------------------------

ALLOWED_IMAGE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".avif",
)

ALLOWED_IMAGE_CDNS = (
    "images.unsplash.com",
    "plus.unsplash.com",
    "res.cloudinary.com",
    "cloudinary.com",
    "amazonaws.com",
    "s3.amazonaws.com",
    "googleusercontent.com",
    "storage.googleapis.com",
    "imgix.net",
)

FORBIDDEN_IMAGE_EXTENSIONS = (
    ".svg",
    ".html",
    ".htm",
    ".js",
    ".php",
    ".exe",
    ".sh",
    ".py",
    ".bat",
    ".cgi",
)


def validate_safe_image_url(url_str: str) -> str:
    """
    Validate a remotely hosted image URL.

    Allowed:
    - HTTPS URLs only
    - JPG/JPEG/PNG/WEBP/AVIF extensions
    - Explicitly allow-listed image CDN hosts

    Blocked:
    - HTTP URLs
    - SVG
    - HTML
    - JavaScript
    - PHP
    - Executable/script extensions
    - Unknown hosts without a recognizable image extension
    """

    if not url_str or not isinstance(url_str, str):
        raise serializers.ValidationError(
            "A valid image URL string is required."
        )

    url_str = url_str.strip()

    if len(url_str) > 500:
        raise serializers.ValidationError(
            "Image URL cannot exceed 500 characters."
        )

    parsed = urlparse(url_str)

    # Only HTTPS is allowed for externally hosted images.
    if parsed.scheme.lower() != "https":
        raise serializers.ValidationError(
            "Image URL must use HTTPS."
        )

    if not parsed.netloc:
        raise serializers.ValidationError(
            "Image URL must contain a valid hostname."
        )

    hostname = parsed.hostname.lower() if parsed.hostname else ""

    if not hostname:
        raise serializers.ValidationError(
            "Image URL must contain a valid hostname."
        )

    path_lower = parsed.path.lower()

    # Explicitly block dangerous file extensions.
    for extension in FORBIDDEN_IMAGE_EXTENSIONS:
        if path_lower.endswith(extension):
            raise serializers.ValidationError(
                f"File type '{extension}' is not permitted."
            )

    # Also block dangerous extensions appearing immediately before
    # a query string.
    for extension in FORBIDDEN_IMAGE_EXTENSIONS:
        if path_lower.endswith(extension):
            raise serializers.ValidationError(
                f"File type '{extension}' is not permitted."
            )

    # Standard image extension.
    has_valid_extension = any(
        path_lower.endswith(extension)
        for extension in ALLOWED_IMAGE_EXTENSIONS
    )

    # Explicitly trusted image CDN.
    is_allowed_cdn = any(
        hostname == cdn or hostname.endswith(f".{cdn}")
        for cdn in ALLOWED_IMAGE_CDNS
    )

    if not (has_valid_extension or is_allowed_cdn):
        raise serializers.ValidationError(
            "Image URL must point to a JPG, JPEG, PNG, WEBP, or AVIF image "
            "or use an approved image CDN."
        )

    return url_str


# ---------------------------------------------------------------------------
# Amenity
# ---------------------------------------------------------------------------

class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = [
            "id",
            "name",
            "slug",
            "icon_name",
        ]


# ---------------------------------------------------------------------------
# Hall Image
# ---------------------------------------------------------------------------

class HallImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = HallImage
        fields = [
            "id",
            "image_url",
            "caption",
            "sort_order",
            "is_primary",
            "created_at",
        ]


# ---------------------------------------------------------------------------
# Hall List
# ---------------------------------------------------------------------------

class HallListSerializer(serializers.ModelSerializer):
    """
    Compact serializer used for:
    - public search results
    - featured halls
    - homepage listings
    """

    primary_image = serializers.ReadOnlyField()
    amenities = AmenitySerializer(
        many=True,
        read_only=True,
    )
    owner_business = serializers.CharField(
        source="owner.owner_profile.business_name",
        read_only=True,
    )

    class Meta:
        model = Hall
        fields = [
            "id",
            "name",
            "slug",
            "address_line1",
            "city",
            "locality",
            "postal_code",
            "latitude",
            "longitude",
            "min_capacity",
            "max_capacity",
            "hall_type",
            "base_price_morning",
            "base_price_evening",
            "base_price_full_day",
            "advance_percentage",
            "catering_policy",
            "veg_plate_price",
            "non_veg_plate_price",
            "decor_price",
            "dj_price",
            "avg_rating",
            "review_count",
            "primary_image",
            "amenities",
            "owner_business",
            "status",
            "approval_status",
            "created_at",
        ]


# ---------------------------------------------------------------------------
# Hall Detail
# ---------------------------------------------------------------------------

class HallDetailSerializer(serializers.ModelSerializer):
    """
    Full hall serializer used by:
    - public hall detail
    - owner hall management
    - admin hall management
    """

    images = HallImageSerializer(
        many=True,
        read_only=True,
    )

    amenities = AmenitySerializer(
        many=True,
        read_only=True,
    )

    owner_name = serializers.CharField(
        source="owner.full_name",
        read_only=True,
    )

    owner_business = serializers.CharField(
        source="owner.owner_profile.business_name",
        read_only=True,
    )

    owner_phone = serializers.CharField(
        source="owner.phone",
        read_only=True,
    )

    class Meta:
        model = Hall
        fields = [
            "id",
            "owner_id",
            "owner_name",
            "owner_business",
            "owner_phone",
            "name",
            "slug",
            "description",
            "address_line1",
            "address_line2",
            "city",
            "locality",
            "postal_code",
            "latitude",
            "longitude",
            "min_capacity",
            "max_capacity",
            "hall_type",
            "base_price_morning",
            "base_price_evening",
            "base_price_full_day",
            "advance_percentage",
            "catering_policy",
            "veg_plate_price",
            "non_veg_plate_price",
            "decor_price",
            "dj_price",
            "cancellation_policy",
            "status",
            "approval_status",
            "rejection_reason",
            "avg_rating",
            "review_count",
            "images",
            "amenities",
            "created_at",
            "updated_at",
        ]


# ---------------------------------------------------------------------------
# Hall Create / Update
# ---------------------------------------------------------------------------

class HallCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer used by owners when creating or updating a hall listing.
    """

    amenity_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True,
    )

    initial_images = serializers.ListField(
        child=serializers.URLField(max_length=500),
        required=False,
        write_only=True,
    )

    class Meta:
        model = Hall

        fields = [
            "name",
            "description",
            "address_line1",
            "address_line2",
            "city",
            "locality",
            "postal_code",
            "latitude",
            "longitude",
            "min_capacity",
            "max_capacity",
            "hall_type",
            "base_price_morning",
            "base_price_evening",
            "base_price_full_day",
            "advance_percentage",
            "catering_policy",
            "veg_plate_price",
            "non_veg_plate_price",
            "decor_price",
            "dj_price",
            "cancellation_policy",
            "amenity_ids",
            "initial_images",
        ]

    def validate_initial_images(self, value):
        """
        Validate all initial gallery images during hall creation.
        """

        if len(value) > 20:
            raise serializers.ValidationError(
                "Maximum 20 images are allowed per listing."
            )

        validated_urls = []

        for url in value:
            validated_urls.append(
                validate_safe_image_url(url)
            )

        return validated_urls

    def validate(self, attrs):
        """
        Validate capacity values while correctly handling partial updates.
        """

        min_capacity = attrs.get(
            "min_capacity",
            getattr(self.instance, "min_capacity", None),
        )

        max_capacity = attrs.get(
            "max_capacity",
            getattr(self.instance, "max_capacity", None),
        )

        if min_capacity is not None and min_capacity <= 0:
            raise serializers.ValidationError(
                {
                    "min_capacity": [
                        "Minimum capacity must be greater than 0."
                    ]
                }
            )

        if (
            min_capacity is not None
            and max_capacity is not None
            and max_capacity < min_capacity
        ):
            raise serializers.ValidationError(
                {
                    "max_capacity": [
                        "Maximum capacity cannot be less than "
                        "minimum capacity."
                    ]
                }
            )

        return attrs

    def create(self, validated_data):
        amenity_ids = validated_data.pop(
            "amenity_ids",
            [],
        )

        initial_images = validated_data.pop(
            "initial_images",
            [],
        )

        owner = self.context["request"].user

        hall = Hall.objects.create(
            owner=owner,
            approval_status=HallApprovalStatus.DRAFT,
            status=HallStatus.ACTIVE,
            **validated_data,
        )

        if amenity_ids:
            amenities = Amenity.objects.filter(
                id__in=amenity_ids,
                is_active=True,
            )

            hall.amenities.set(amenities)

        if initial_images:
            HallImage.objects.bulk_create(
                [
                    HallImage(
                        hall=hall,
                        image_url=image_url,
                        sort_order=index,
                        is_primary=(index == 0),
                    )
                    for index, image_url in enumerate(initial_images)
                ]
            )

        return hall

    def update(self, instance, validated_data):
        amenity_ids = validated_data.pop(
            "amenity_ids",
            None,
        )

        # initial_images is intentionally ignored during PATCH.
        # Gallery management has dedicated endpoints.
        validated_data.pop(
            "initial_images",
            None,
        )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if amenity_ids is not None:
            amenities = Amenity.objects.filter(
                id__in=amenity_ids,
                is_active=True,
            )

            instance.amenities.set(amenities)

        return instance


# ---------------------------------------------------------------------------
# Admin Approval
# ---------------------------------------------------------------------------

class AdminHallApprovalSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=[
            "APPROVE",
            "REJECT",
            "SUSPEND",
        ]
    )

    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000,
    )

    def validate(self, attrs):
        action = attrs.get("action")
        reason = (attrs.get("reason") or "").strip()

        if action == "REJECT" and not reason:
            raise serializers.ValidationError(
                {
                    "reason": [
                        "Rejection reason is mandatory "
                        "when rejecting a listing."
                    ]
                }
            )

        attrs["reason"] = reason

        return attrs