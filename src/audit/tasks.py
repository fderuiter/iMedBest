import logging

from celery import shared_task
from django.db.utils import OperationalError

from .models import AuditLog

logger = logging.getLogger(__name__)


@shared_task
def create_audit_log_task(action, model_name, object_id, audit_context=None):
    if audit_context is None:
        audit_context = {}

    try:
        valid_fields = {f.name for f in AuditLog._meta.get_fields()}

        create_kwargs = {
            "action": action,
            "model_name": model_name,
            "object_id": object_id,
        }
        for k, v in audit_context.items():
            if k in valid_fields:
                create_kwargs[k] = v

        AuditLog.objects.create(**create_kwargs)
    except OperationalError as e:
        logger.error(f"Failed to create audit log: {e}")
