import logging
from apps.core.models import AuditLog

logger = logging.getLogger(__name__)

class AuditService:
    @staticmethod
    def log_action(actor, action: str, obj=None, object_type: str = None, object_id: str = None, ip_address: str = None, user_agent: str = None, changes: dict = None):
        """
        Record an immutable entry in the system audit log.
        """
        try:
            target_type = object_type or (obj.__class__.__name__ if obj else "System")
            target_id = object_id or (str(obj.pk) if obj and hasattr(obj, "pk") else "0")

            return AuditLog.objects.create(
                actor=actor if actor and getattr(actor, "is_authenticated", False) else None,
                action=action,
                object_type=target_type,
                object_id=target_id,
                ip_address=ip_address,
                user_agent=(user_agent or "")[:500],
                changes=changes or {}
            )
        except Exception as exc:
            logger.error(f"Failed to record audit log: {exc}", exc_info=True)
            return None
