import structlog
from django.db import IntegrityError, transaction

from clinical.models import Record, Study, Subject
from clinical.utils import parse_imednet_date_array
from core.models import Form, Interval, IntervalForm, RecordRevision, User, UserRole, Variable

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

                    _, created = Form.objects.update_or_create(
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
                        },
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
                logger.error("form_sync_failed", imednet_id=item.get("formId"), error=str(e), payload=item)
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
                        raise ValueError(f"Missing related entity: {e!s}") from e

                    _, created = RecordRevision.objects.update_or_create(
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
                        },
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
                    "record_revision_sync_failed", imednet_id=item.get("recordRevisionId"), error=str(e), payload=item
                )
                continue

        return stats

    @staticmethod
    def sync_variables(study: Study, data_list: list[dict]) -> dict:
        """
        Synchronizes variable metadata from iMednet.
        Uses update_or_create for idempotency based on imednet_id.
        Handles soft-deletion for variables missing from the payload.
        """
        stats = {"created": 0, "updated": 0, "failed": 0, "soft_deleted": 0}
        synced_imednet_ids = []

        for item in data_list:
            try:
                with transaction.atomic():
                    imednet_id = str(item.get("variableId"))
                    form_id_ext = str(item.get("formId")) if item.get("formId") else None

                    form = None
                    if form_id_ext:
                        try:
                            form = Form.objects.get(study=study, imednet_id=form_id_ext)
                        except Form.DoesNotExist:
                            logger.warning(
                                "variable_sync_missing_form",
                                variable_id=imednet_id,
                                form_id=form_id_ext,
                                study_id=study.id,
                            )

                    _, created = Variable.objects.update_or_create(
                        imednet_id=imednet_id,
                        defaults={
                            "study": study,
                            "form": form,
                            "form_key_raw": form_id_ext or "",
                            "variable_type": item.get("variableType"),
                            "variable_name": item.get("variableName"),
                            "sequence": item.get("sequence"),
                            "revision": item.get("revision"),
                            "disabled": item.get("disabled", False),
                            "variable_oid": item.get("variableOid"),
                            "deleted": item.get("deleted", False),
                            "label": item.get("label", ""),
                            "blinded": item.get("blinded", False),
                        },
                    )

                    synced_imednet_ids.append(imednet_id)

                    if created:
                        stats["created"] += 1
                        logger.info("variable_created", imednet_id=imednet_id, study_id=study.id)
                    else:
                        stats["updated"] += 1
                        logger.info("variable_updated", imednet_id=imednet_id, study_id=study.id)

            except (IntegrityError, ValueError, TypeError) as e:
                stats["failed"] += 1
                logger.error("variable_sync_failed", imednet_id=item.get("variableId"), error=str(e), payload=item)
                continue

        # Handle soft-deletion for missing records
        to_soft_delete = Variable.objects.filter(study=study, deleted=False).exclude(imednet_id__in=synced_imednet_ids)
        soft_delete_count = to_soft_delete.update(deleted=True)
        stats["soft_deleted"] = soft_delete_count

        if soft_delete_count > 0:
            logger.info("variables_soft_deleted", count=soft_delete_count, study_id=study.id)

        return stats

    @staticmethod
    def sync_intervals(study: Study, data_list: list[dict]) -> dict:
        """
        Synchronizes interval metadata and their associated forms from iMednet.
        Uses update_or_create for idempotency based on imednet_id.
        Handles soft-deletion for intervals missing from the payload.
        """
        stats = {"created": 0, "updated": 0, "failed": 0, "soft_deleted": 0}
        synced_imednet_ids = []

        for item in data_list:
            try:
                with transaction.atomic():
                    imednet_id = str(item.get("intervalId"))

                    interval, created = Interval.objects.update_or_create(
                        imednet_id=imednet_id,
                        defaults={
                            "study": study,
                            "interval_name": item.get("intervalName"),
                            "interval_description": item.get("intervalDescription", ""),
                            "interval_sequence": item.get("intervalSequence"),
                            "interval_group_id": item.get("intervalGroupId"),
                            "interval_group_name": item.get("intervalGroupName"),
                            "timeline": item.get("timeline"),
                            "defined_using_interval": item.get("definedUsingInterval", ""),
                            "window_calculation_form": item.get("windowCalculationForm", ""),
                            "window_calculation_date": item.get("windowCalculationDate", ""),
                            "actual_date_form": item.get("actualDateForm", ""),
                            "actual_date": item.get("actualDate", ""),
                            "due_date_will_be_in": item.get("dueDateWillBeIn"),
                            "negative_slack": item.get("negativeSlack"),
                            "positive_slack": item.get("positiveSlack"),
                            "epro_grace_period": item.get("eproGracePeriod"),
                            "disabled": item.get("disabled", False),
                        },
                    )

                    # Rebuild forms junction
                    # We only link forms that already exist in our database
                    IntervalForm.objects.filter(interval=interval).delete()
                    forms_data = item.get("forms", [])
                    if isinstance(forms_data, list):
                        for form_item in forms_data:
                            form_id_ext = str(form_item.get("formId"))
                            try:
                                form = Form.objects.get(study=study, imednet_id=form_id_ext)
                                IntervalForm.objects.create(interval=interval, form=form)
                            except Form.DoesNotExist:
                                logger.warning(
                                    "interval_form_sync_missing_form",
                                    interval_id=imednet_id,
                                    form_id=form_id_ext,
                                    study_id=study.id,
                                )

                    synced_imednet_ids.append(imednet_id)

                    if created:
                        stats["created"] += 1
                        logger.info("interval_created", imednet_id=imednet_id, study_id=study.id)
                    else:
                        stats["updated"] += 1
                        logger.info("interval_updated", imednet_id=imednet_id, study_id=study.id)

            except (IntegrityError, ValueError, TypeError) as e:
                stats["failed"] += 1
                logger.error("interval_sync_failed", imednet_id=item.get("intervalId"), error=str(e), payload=item)
                continue

        # Handle soft-deletion for missing records
        to_soft_delete = Interval.objects.filter(study=study, disabled=False).exclude(imednet_id__in=synced_imednet_ids)
        soft_delete_count = to_soft_delete.update(disabled=True)
        stats["soft_deleted"] = soft_delete_count

        if soft_delete_count > 0:
            logger.info("intervals_soft_deleted", count=soft_delete_count, study_id=study.id)

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
                        },
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
                logger.error("user_sync_failed", imednet_id=item.get("userId"), error=str(e), payload=item)
                continue

        return stats
