import uuid
from django.db import models
from django.conf import settings
from django.utils.text import slugify
from apps.core.models import TimeStampedModel, UUIDModel

class HallApprovalStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'
    SUSPENDED = 'SUSPENDED', 'Suspended'
    DEACTIVATED = 'DEACTIVATED', 'Deactivated'


class HallStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    INACTIVE = 'INACTIVE', 'Inactive'


class HallType(models.TextChoices):
    AC = 'AC', 'AC Banquet Hall'
    NON_AC = 'NON_AC', 'Non-AC Hall'
    OPEN_LAWN = 'OPEN_LAWN', 'Open Lawn'
    HYBRID = 'HYBRID', 'Hybrid (Lawn & Hall)'
    CONVENTION = 'CONVENTION', 'Convention Center'


class CateringPolicy(models.TextChoices):
    IN_HOUSE_ONLY = 'IN_HOUSE_ONLY', 'In-house Catering Only'
    OUTSIDE_ALLOWED = 'OUTSIDE_ALLOWED', 'Outside Catering Allowed'
    BOTH = 'BOTH', 'In-house & Outside Allowed'


class CancellationPolicy(models.TextChoices):
    FLEXIBLE = 'FLEXIBLE', 'Tier 1: > 90 days out (95% refund minus 5% fee)'
    MODERATE = 'MODERATE', 'Tier 2: 30 to 90 days out (50% refund)'
    STRICT = 'STRICT', 'Tier 3: < 30 days out (0% refund)'


class Amenity(UUIDModel, TimeStampedModel):
    """Standardized catalog of hall facilities and amenities."""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    icon_name = models.CharField(max_length=50, blank=True, default="CheckCircle2")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'amenities'
        ordering = ['name']
        verbose_name_plural = 'Amenities'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Hall(UUIDModel, TimeStampedModel):
    """
    Authoritative Function Hall Model.
    """
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='halls'
    )
    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=280, unique=True, blank=True, db_index=True)
    description = models.TextField(blank=True, default="")

    # Location Information
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100, default="Hyderabad", db_index=True)
    locality = models.CharField(max_length=100, db_index=True)
    postal_code = models.CharField(max_length=20, default="500081")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Capacity & Specifications
    min_capacity = models.PositiveIntegerField(default=100)
    max_capacity = models.PositiveIntegerField(default=500)
    hall_type = models.CharField(
        max_length=30,
        choices=HallType.choices,
        default=HallType.AC,
        db_index=True
    )

    # Pricing Structure (Morning, Evening, Full Day slots)
    base_price_morning = models.DecimalField(max_digits=12, decimal_places=2, default=30000.00)
    base_price_evening = models.DecimalField(max_digits=12, decimal_places=2, default=45000.00)
    base_price_full_day = models.DecimalField(max_digits=12, decimal_places=2, default=70000.00)
    advance_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=20.00)

    # Catering & Addons
    catering_policy = models.CharField(
        max_length=30,
        choices=CateringPolicy.choices,
        default=CateringPolicy.BOTH
    )
    veg_plate_price = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    non_veg_plate_price = models.DecimalField(max_digits=10, decimal_places=2, default=750.00)
    decor_price = models.DecimalField(max_digits=10, decimal_places=2, default=15000.00)
    dj_price = models.DecimalField(max_digits=10, decimal_places=2, default=10000.00)

    # Policies
    cancellation_policy = models.CharField(
        max_length=30,
        choices=CancellationPolicy.choices,
        default=CancellationPolicy.MODERATE
    )

    # Operational & Approval States
    status = models.CharField(
        max_length=20,
        choices=HallStatus.choices,
        default=HallStatus.ACTIVE,
        db_index=True
    )
    approval_status = models.CharField(
        max_length=20,
        choices=HallApprovalStatus.choices,
        default=HallApprovalStatus.DRAFT,
        db_index=True
    )
    rejection_reason = models.TextField(blank=True, default="")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_halls'
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # Relationships
    amenities = models.ManyToManyField(Amenity, related_name='halls', blank=True)

    # Aggregated metrics for high-speed browsing
    avg_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    review_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'halls'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['city', 'locality', 'approval_status', 'status']),
            models.Index(fields=['min_capacity', 'max_capacity']),
            models.Index(fields=['approval_status', 'status']),
            models.Index(fields=['slug']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(max_capacity__gte=models.F('min_capacity')) & models.Q(min_capacity__gt=0),
                name='chk_hall_capacity'
            ),
            models.CheckConstraint(
                condition=models.Q(advance_percentage__gte=0.00) & models.Q(advance_percentage__lte=100.00),
                name='chk_advance_pct'
            ),
            models.CheckConstraint(
                condition=models.Q(base_price_morning__gte=0) & models.Q(base_price_evening__gte=0) & models.Q(base_price_full_day__gte=0),
                name='chk_base_prices_positive'
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(f"{self.name} {self.locality} {self.city}")
            candidate = base_slug
            counter = 1
            while Hall.objects.filter(slug=candidate).exclude(id=self.id).exists():
                candidate = f"{base_slug}-{counter}"
                counter += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.locality}, {self.city}) [{self.approval_status}]"

    @property
    def is_publicly_visible(self):
        return self.approval_status == HallApprovalStatus.APPROVED and self.status == HallStatus.ACTIVE

    @property
    def primary_image(self):
        primary = self.images.filter(is_primary=True).first()
        if not primary:
            primary = self.images.first()
        return primary.image_url if primary else "https://images.unsplash.com/photo-1519167758481-83f550bb49b3?auto=format&fit=crop&w=800&q=80"


class HallImage(UUIDModel, TimeStampedModel):
    """Gallery imagery for function halls."""
    hall = models.ForeignKey(
        Hall,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image_url = models.URLField(max_length=500)
    caption = models.CharField(max_length=255, blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = 'hall_images'
        ordering = ['sort_order', 'created_at']

    def save(self, *args, **kwargs):
        if self.is_primary:
            # Unmark other primary images for this hall
            HallImage.objects.filter(hall=self.hall, is_primary=True).exclude(id=self.id).update(is_primary=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Image for {self.hall.name} (order: {self.sort_order})"
