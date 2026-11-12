from datetime import datetime, timezone
from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel, UUIDModel
from apps.bookings.models import Booking
from apps.halls.models import Hall

class Review(UUIDModel, TimeStampedModel):
    """
    Verified customer review on a completed function hall booking.
    Strictly one review per booking.
    """
    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name='review'
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    hall = models.ForeignKey(
        Hall,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    rating = models.PositiveSmallIntegerField(
        help_text="Star rating between 1 and 5"
    )
    comment = models.TextField()
    owner_response = models.TextField(blank=True, default="")
    owner_responded_at = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'reviews'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['hall', 'is_published', '-created_at']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=1) & models.Q(rating__lte=5),
                name='chk_review_rating_1_to_5'
            )
        ]

    def __str__(self):
        return f"Review by {self.customer.full_name} for {self.hall.name} ({self.rating}★)"

    def update_hall_aggregates(self):
        """Recalculates average rating and review count for the hall."""
        published_reviews = Review.objects.filter(hall=self.hall, is_published=True)
        count = published_reviews.count()
        if count > 0:
            avg = published_reviews.aggregate(models.Avg('rating'))['rating__avg'] or 0.0
            self.hall.avg_rating = round(avg, 2)
            self.hall.review_count = count
        else:
            self.hall.avg_rating = 0.0
            self.hall.review_count = 0
        self.hall.save(update_fields=['avg_rating', 'review_count'])

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.update_hall_aggregates()

    def delete(self, *args, **kwargs):
        hall = self.hall
        super().delete(*args, **kwargs)
        # Recalculate aggregates on deletion
        published_reviews = Review.objects.filter(hall=hall, is_published=True)
        count = published_reviews.count()
        if count > 0:
            avg = published_reviews.aggregate(models.Avg('rating'))['rating__avg'] or 0.0
            hall.avg_rating = round(avg, 2)
            hall.review_count = count
        else:
            hall.avg_rating = 0.0
            hall.review_count = 0
        hall.save(update_fields=['avg_rating', 'review_count'])
