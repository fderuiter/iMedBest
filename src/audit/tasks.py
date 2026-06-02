import logging

from celery import shared_task
from django.db.utils import OperationalError

from .models import AuditLog

logger = logging.getLogger(__name__)


@shared_task
def create_audit_log_task(action, model_name, object_id, changes, user_id, ip_address, user_agent):  # noqa: PLR0913
    try:
        AuditLog.objects.create(
            action=action,
            model_name=model_name,
            object_id=object_id,
            changes=changes,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except OperationalError as e:
        logger.error(f"Failed to create audit log: {e}")
