import logging

from celery import shared_task
from django.db.utils import OperationalError

from .models import AuditLog

logger = logging.getLogger(__name__)


@shared_task
def create_audit_log_task(
    action, model_name, object_id, changes, user_id, ip_address, user_agent, study_id=None,
    agent_did=None, supervisor_did=None, external_transaction_id=None,
    cryptographic_signature=None, rejection_reason=None
):  # noqa: PLR0913
    try:
        AuditLog.objects.create(
            action=action,
            model_name=model_name,
            object_id=object_id,
            changes=changes,
            user_id=user_id,
            study_id=study_id,
            ip_address=ip_address,
            user_agent=user_agent,
            agent_did=agent_did,
            supervisor_did=supervisor_did,
            external_transaction_id=external_transaction_id,
            cryptographic_signature=cryptographic_signature,
            rejection_reason=rejection_reason,
        )
    except OperationalError as e:
        logger.error(f"Failed to create audit log: {e}")
