import structlog
from django.db import IntegrityError, transaction
from core.models import Form, User, UserRole, RecordRevision
from clinical.models import Study, Subject, Record
from clinical.utils import parse_imednet_date_array

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

    @staticmethod
    def sync_record_revisions(study: Study, data_list: list[dict]) -> dict:
        """
        Synchronizes record revision metadata from iMednet.
        Uses update_or_create for idempotency based on imednet_id.
        """
        stats = {"created": 0, "updated": 0, "failed": 0}

        for item in data_list:
            try:
                with transaction.atomic():
                    imednet_id = str(item.get("recordRevisionId"))

                    # Lookup related entities by their external IDs
                    # We expect these to exist due to sync order, but handle if missing
                    subject_id_ext = str(item.get("subjectId"))
                    record_id_ext = str(item.get("recordId"))
                    user_id_ext = str(item.get("userId"))

                    try:
                        subject = Subject.all_objects.get(provider=study.provider, external_id=subject_id_ext)
                        record = Record.all_objects.get(provider=study.provider, external_id=record_id_ext)
                        user_profile = User.objects.get(study=study, imednet_id=user_id_ext)
                    except (Subject.DoesNotExist, Record.DoesNotExist, User.DoesNotExist) as e:
                        raise ValueError(f"Missing related entity: {str(e)}") from e

                    revision, created = RecordRevision.objects.update_or_create(
                        imednet_id=imednet_id,
                        defaults={
                            "study": study,
                            "subject": subject,
                            "record": record,
                            "user_profile": user_profile,
                            "imednet_record_id": item.get("recordId"),
                            "record_oid": item.get("recordOid"),
                            "record_revision": item.get("recordRevision"),
                            "data_revision": item.get("dataRevision"),
                            "record_status": item.get("recordStatus"),
                            "imednet_subject_id": item.get("subjectId"),
                            "subject_oid": item.get("subjectOid"),
                            "subject_key": item.get("subjectKey"),
                            "site_id": item.get("siteId"),
                            "form_key": item.get("formKey"),
                            "interval_id": item.get("intervalId"),
                            "role": item.get("role"),
                            "user_raw": item.get("user"),
                            "reason_for_change": item.get("reasonForChange", ""),
                            "deleted": item.get("deleted", False),
                        }
                    )

                    if created:
                        stats["created"] += 1
                        logger.info("record_revision_created", imednet_id=imednet_id, study_id=study.id)
                    else:
                        stats["updated"] += 1
                        logger.info("record_revision_updated", imednet_id=imednet_id, study_id=study.id)

            except (IntegrityError, ValueError, TypeError) as e:
                stats["failed"] += 1
                logger.error(
                    "record_revision_sync_failed",
                    imednet_id=item.get("recordRevisionId"),
                    error=str(e),
                    payload=item
                )
                continue

        return stats

    @staticmethod
    def sync_users(study: Study, data_list: list[dict]) -> dict:
        """
        Synchronizes user metadata and roles from iMednet.
        Uses update_or_create for idempotency based on imednet_id.
        """
        stats = {"created": 0, "updated": 0, "failed": 0}

        for item in data_list:
            try:
                with transaction.atomic():
                    imednet_id = str(item.get("userId"))
                    user, created = User.objects.update_or_create(
                        imednet_id=imednet_id,
                        defaults={
                            "study": study,
                            "login": item.get("login"),
                            "first_name": item.get("firstName"),
                            "last_name": item.get("lastName"),
                            "email": item.get("email"),
                            "user_active_in_study": item.get("userActiveInStudy", True),
                        }
                    )

                    # Rebuild roles
                    user.roles.all().delete()
                    roles_data = item.get("roles", [])
                    if isinstance(roles_data, list):
                        for role_item in roles_data:
                            UserRole.objects.create(
                                user=user,
                                role_name=role_item.get("roleName"),
                                start_date=parse_imednet_date_array(role_item.get("startDate")),
                                end_date=parse_imednet_date_array(role_item.get("endDate")),
                            )

                    if created:
                        stats["created"] += 1
                        logger.info("user_created", imednet_id=imednet_id, study_id=study.id)
                    else:
                        stats["updated"] += 1
                        logger.info("user_updated", imednet_id=imednet_id, study_id=study.id)

            except (IntegrityError, ValueError, TypeError) as e:
                stats["failed"] += 1
                logger.error(
                    "user_sync_failed",
                    imednet_id=item.get("userId"),
                    error=str(e),
                    payload=item
                )
                continue

        return stats
