import structlog
from django.db import IntegrityError, transaction
from core.models import Form
from clinical.models import Study

logger = structlog.get_logger(__name__)

class StudySyncEngine:
    """
    Handles synchronization of clinical entities from external providers.
    """

    @staticmethod
    def sync_forms(study: Study, data_list: list[dict]) -> dict:
        """
        Synchronizes form metadata from iMednet.
        Uses update_or_create for idempotency based on imednet_id.
        Handles soft-deletion for forms missing from the payload.
        """
        stats = {"created": 0, "updated": 0, "failed": 0, "soft_deleted": 0}
        synced_imednet_ids = []

        for item in data_list:
            try:
                with transaction.atomic():
                    # Map API payload to model fields
                    imednet_id = str(item.get("formId"))

                    form, created = Form.objects.update_or_create(
                        imednet_id=imednet_id,
                        defaults={
                            "study": study,
                            "form_key": item.get("formKey"),
                            "form_name": item.get("formName"),
                            "form_type": item.get("formType"),
                            "revision": item.get("revision"),
                            "embedded_log": item.get("embeddedLog", False),
                            "enforce_ownership": item.get("enforceOwnership", False),
                            "user_agreement": item.get("userAgreement", False),
                            "subject_record_report": item.get("subjectRecordReport", False),
                            "unscheduled_visit": item.get("unscheduledVisit", False),
                            "other_forms": item.get("otherForms", False),
                            "epro_form": item.get("eproForm", False),
                            "allow_copy": item.get("allowCopy", False),
                            "disabled": item.get("disabled", False),
                        }
                    )

                    synced_imednet_ids.append(imednet_id)

                    if created:
                        stats["created"] += 1
                        logger.info("form_created", imednet_id=imednet_id, study_id=study.id)
                    else:
                        stats["updated"] += 1
                        logger.info("form_updated", imednet_id=imednet_id, study_id=study.id)

            except (IntegrityError, ValueError, TypeError) as e:
                stats["failed"] += 1
                logger.error(
                    "form_sync_failed",
                    imednet_id=item.get("formId"),
                    error=str(e),
                    payload=item
                )
                continue

        # Handle soft-deletion for missing records
        # If a form is not in the current payload but exists locally for this study, mark it as disabled
        to_soft_delete = Form.objects.filter(study=study, disabled=False).exclude(imednet_id__in=synced_imednet_ids)
        soft_delete_count = to_soft_delete.update(disabled=True)
        stats["soft_deleted"] = soft_delete_count

        if soft_delete_count > 0:
            logger.info("forms_soft_deleted", count=soft_delete_count, study_id=study.id)

        return stats
