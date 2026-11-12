import uuid
from django.db import models
from django.conf import settings

class TimeStampedModel(models.Model):
    """Abstract base model with auto-managed created_at and updated_at timestamps."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """Abstract base model with non-enumerable UUIDv4 primary key."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class PlatformSetting(TimeStampedModel):
    """Configurable business parameters (commission rate, tax rate, hold duration, etc.)."""
    key = models.CharField(max_length=100, unique=True, db_index=True)
    value = models.JSONField(help_text="Arbitrary typed JSON payload for platform setting value")
    description = models.TextField(blank=True, default="")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_settings"
    )

    class Meta:
        db_table = "platform_settings"
        ordering = ["key"]
        verbose_name = "Platform Setting"
        verbose_name_plural = "Platform Settings"

    def __str__(self):
        return f"{self.key}: {self.value}"


class AuditLog(models.Model):
    """Immutable audit trail of all high-value administrative and financial operations."""
    id = models.BigAutoField(primary_key=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs"
    )
    action = models.CharField(max_length=100, db_index=True)
    object_type = models.CharField(max_length=100, db_index=True)
    object_id = models.CharField(max_length=100, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True, default="")
    changes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["object_type", "object_id"]),
        ]

    def __str__(self):
        actor_name = self.actor.email if self.actor else "SYSTEM"
        return f"[{self.created_at}] {actor_name} -> {self.action} on {self.object_type}:{self.object_id}"
