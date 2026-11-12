from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel, UUIDModel
from apps.halls.models import Hall

class Favorite(UUIDModel, TimeStampedModel):
    """
    Customer saved / bookmarked function halls.
    """
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='favorites'
    )
    hall = models.ForeignKey(
        Hall,
        on_delete=models.CASCADE,
        related_name='favorited_by'
    )

    class Meta:
        db_table = 'favorites'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['customer', 'hall'],
                name='unique_customer_favorite_hall'
            )
        ]

    def __str__(self):
        return f"{self.customer.email} saved {self.hall.name}"
