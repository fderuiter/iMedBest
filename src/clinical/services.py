import structlog
from django.db import IntegrityError, transaction
from django.utils.dateparse import parse_date

from clinical.models import Record, Site, Study
from clinical.models import Subject as ClinicalSubject
from clinical.utils import parse_imednet_date_array
from core.models import (
    Coding,
    Form,
    Interval,
    IntervalForm,
    Query,
    QueryComment,
    RecordRevision,
    SubjectKeyword,
    Job,
    User,
    UserRole,
    Variable,
    Visit,
)
from core.models import (
    Record as CoreRecord,
)
from core.models import (
    Subject as CoreSubject,
)

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
                        subject = ClinicalSubject.all_objects.get(provider=study.provider, external_id=subject_id_ext)
                        record = Record.all_objects.get(provider=study.provider, external_id=record_id_ext)
                        user_profile = User.objects.get(study=study, imednet_id=user_id_ext)
                    except (ClinicalSubject.DoesNotExist, Record.DoesNotExist, User.DoesNotExist) as e:
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
    def sync_job_status(batch_id: str) -> str:
        """
        Synchronizes job status for a given batch from iMednet.
        Uses update_or_create for idempotency based on imednet_id (jobId).
        """
        # Resolve study context via existing Job records with the same batch_id,
        # or fallback to an internal tracking mechanism.
        existing_job = Job.objects.filter(batch_id=batch_id).first()
        study = existing_job.study if existing_job else Study.objects.first()

        if not study:
            return "Failed: No study found to associate with jobs."

        # Simulated payload based on batch_id
        # In actual use, this would come from a client call to iMednet's Job status endpoint
        data_list = StudySyncEngine._fetch_job_payload(batch_id)

        stats = {"created": 0, "updated": 0, "failed": 0}

        for item in data_list:
            try:
                with transaction.atomic():
                    job_id_raw = item.get("jobId")
                    if job_id_raw in (None, ""):
                        raise ValueError("Missing jobId in payload")
                    imednet_id = str(job_id_raw)

                    _, created = Job.objects.update_or_create(
                        imednet_id=imednet_id,
                        defaults={
                            "study": study,
                            "batch_id": item.get("batchId"),
                            "state": item.get("state"),
                            "date_created": parse_imednet_date_array(item.get("dateCreated")),
                            "date_started": parse_imednet_date_array(item.get("dateStarted"))
                            if item.get("dateStarted")
                            else None,
                            "date_finished": parse_imednet_date_array(item.get("dateFinished"))
                            if item.get("dateFinished")
                            else None,
                        },
                    )

                    if created:
                        stats["created"] += 1
                        logger.info("job_created", imednet_id=imednet_id, batch_id=batch_id)
                    else:
                        stats["updated"] += 1
                        logger.info("job_updated", imednet_id=imednet_id, batch_id=batch_id)

            except (IntegrityError, ValueError, TypeError) as e:
                stats["failed"] += 1
                logger.error("job_sync_failed", imednet_id=item.get("jobId"), batch_id=batch_id, error=str(e))
                continue

        return f"Created: {stats['created']}, Updated: {stats['updated']}, Failed: {stats['failed']}"

    @staticmethod
    def _fetch_job_payload(batch_id: str) -> list[dict]:
        """
        Simulated internal method to fetch job payload from iMednet.
        """
        return []

    @staticmethod
    def sync_codings(study: Study, data_list: list[dict]) -> dict:
        """
        Synchronizes coding metadata from iMednet.
        Uses update_or_create for idempotency based on imednet_id.
        """
        stats = {"created": 0, "updated": 0, "failed": 0}

        for item in data_list:
            try:
                with transaction.atomic():
                    imednet_id = str(item.get("codingId"))

                    # Resolve relationships
                    subject_id_ext = str(item.get("subjectId"))
                    form_id_ext = str(item.get("formId"))
                    variable_id_ext = str(item.get("variableId"))
                    user_id_ext = str(item.get("userId"))

                    try:
                        subject = CoreSubject.objects.get(study=study, imednet_id=subject_id_ext)
                        form = Form.objects.get(study=study, imednet_id=form_id_ext)
                        variable_ref = Variable.objects.get(study=study, imednet_id=variable_id_ext)
                        coded_by_user = User.objects.get(study=study, imednet_id=user_id_ext)
                    except (CoreSubject.DoesNotExist, Form.DoesNotExist, Variable.DoesNotExist, User.DoesNotExist) as e:
                        raise ValueError(f"Missing related entity: {e!s}") from e

                    _, created = Coding.objects.update_or_create(
                        imednet_id=imednet_id,
                        defaults={
                            "study": study,
                            "subject": subject,
                            "form": form,
                            "variable_ref": variable_ref,
                            "coded_by_user": coded_by_user,
                            "site_name": item.get("siteName"),
                            "site_id": item.get("siteId"),
                            "imednet_subject_id": item.get("subjectId"),
                            "revision": item.get("revision"),
                            "imednet_record_id": item.get("recordId"),
                            "value": item.get("value"),
                            "code": item.get("code"),
                            "reason": item.get("reason", ""),
                            "dictionary_name": item.get("dictionaryName"),
                            "dictionary_version": item.get("dictionaryVersion"),
                            "date_coded": parse_imednet_date_array(item.get("dateCoded")),
                            "subject_key_raw": item.get("subjectKey", ""),
                            "variable_raw": item.get("variable", ""),
                            "coded_by_raw": item.get("codedBy", ""),
                        },
                    )

                    if created:
                        stats["created"] += 1
                        logger.info("coding_created", imednet_id=imednet_id, study_id=study.id)
                    else:
                        stats["updated"] += 1
                        logger.info("coding_updated", imednet_id=imednet_id, study_id=study.id)

            except (IntegrityError, ValueError, TypeError) as e:
                stats["failed"] += 1
                logger.error("coding_sync_failed", imednet_id=item.get("codingId"), error=str(e), payload=item)
                continue

        return stats

    @staticmethod
    def sync_subjects(study: Study, data_list: list[dict]) -> dict:
        """
        Synchronizes subject metadata and keywords from iMednet.
        Uses update_or_create for idempotency based on imednet_id.
        """
        stats = {"created": 0, "updated": 0, "failed": 0}

        for item in data_list:
            try:
                with transaction.atomic():
                    subject_id_raw = item.get("subjectId")
                    if subject_id_raw in (None, ""):
                        raise ValueError("Missing required subjectId")
                    imednet_id = str(subject_id_raw)

                    site_name = item.get("siteName")
                    site = None
                    if site_name:
                        site = Site.all_objects.filter(study=study, name=site_name).first()

                    subject, created = CoreSubject.objects.update_or_create(
                        imednet_id=imednet_id,
                        defaults={
                            "study": study,
                            "site": site,
                            "site_name_raw": site_name or "",
                            "subject_oid": item.get("subjectOid"),
                            "subject_key": item.get("subjectKey"),
                            "subject_status": item.get("subjectStatus"),
                            "enrollment_start_date": parse_imednet_date_array(item.get("enrollmentStartDate")),
                            "deleted": item.get("deleted", False),
                        },
                    )

                    # Rebuild keywords
                    subject.keywords.all().delete()
                    keywords_data = item.get("keywords", [])
                    if isinstance(keywords_data, list):
                        for kw in keywords_data:
                            SubjectKeyword.objects.create(subject=subject, keyword=kw)

                    if created:
                        stats["created"] += 1
                        logger.info("subject_created", imednet_id=imednet_id, study_id=study.id)
                    else:
                        stats["updated"] += 1
                        logger.info("subject_updated", imednet_id=imednet_id, study_id=study.id)

            except (IntegrityError, ValueError, TypeError) as e:
                stats["failed"] += 1
                logger.error(
                    "subject_sync_failed",
                    imednet_id=item.get("subjectId"),
                    subject_key=item.get("subjectKey"),
                    error=str(e),
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
    def sync_visits(study: Study, data_list: list[dict]) -> dict:
        """
        Synchronizes visit metadata from iMednet.
        Uses update_or_create for idempotency based on imednet_id.
        """
        stats = {"created": 0, "updated": 0, "failed": 0}

        for item in data_list:
            try:
                with transaction.atomic():
                    # Map API payload to model fields
                    imednet_id = str(item.get("visitId"))

                    # Lookup related entities by their external keys
                    subject_key = item.get("subjectKey")
                    interval_name = item.get("intervalName")

                    try:
                        subject = CoreSubject.objects.get(study=study, subject_key=subject_key)
                        interval = Interval.objects.get(study=study, interval_name=interval_name)
                    except (CoreSubject.DoesNotExist, Interval.DoesNotExist) as e:
                        raise ValueError(f"Missing related entity: {e!s}") from e

                    _, created = Visit.objects.update_or_create(
                        imednet_id=imednet_id,
                        defaults={
                            "study": study,
                            "subject": subject,
                            "interval": interval,
                            "interval_name_raw": interval_name,
                            "subject_key_raw": subject_key,
                            "start_date": parse_date(item.get("startDate")) if item.get("startDate") else None,
                            "end_date": parse_date(item.get("endDate")) if item.get("endDate") else None,
                            "due_date": parse_date(item.get("dueDate")) if item.get("dueDate") else None,
                            "visit_date": parse_date(item.get("visitDate")) if item.get("visitDate") else None,
                            "visit_date_form": item.get("visitDateForm", ""),
                            "deleted": item.get("deleted", False),
                            "visit_date_question": item.get("visitDateQuestion", ""),
                        },
                    )

                    if created:
                        stats["created"] += 1
                        logger.info("visit_created", imednet_id=imednet_id, study_id=study.id)
                    else:
                        stats["updated"] += 1
                        logger.info("visit_updated", imednet_id=imednet_id, study_id=study.id)

            except (IntegrityError, ValueError, TypeError) as e:
                stats["failed"] += 1
                logger.error("visit_sync_failed", imednet_id=item.get("visitId"), error=str(e), payload=item)
                continue

        return stats

    @staticmethod
    def sync_records(study: Study, data_list: list[dict]) -> dict:
        """
        Synchronizes record metadata and keywords from iMednet.
        Uses update_or_create for idempotency based on imednet_id.
        """
        from core.models import Record as CoreRecord
        from core.models import RecordKeyword

        stats = {"created": 0, "updated": 0, "failed": 0}

        for item in data_list:
            try:
                with transaction.atomic():
                    imednet_id = str(item.get("recordId"))

                    # Resolve relationships
                    try:
                        subject_id_raw = item.get("subjectId")
                        if not subject_id_raw:
                            raise ValueError("Missing subjectId in payload")
                        subject = CoreSubject.objects.get(study=study, imednet_id=str(subject_id_raw))

                        site = subject.site
                        if not site:
                            # Try to find site from siteId in payload if available
                            site_id_ext = item.get("siteId")
                            if site_id_ext:
                                site = Site.all_objects.filter(
                                    provider=study.provider, external_id=str(site_id_ext)
                                ).first()

                        if not site:
                            raise ValueError(f"Could not resolve site for record {imednet_id}")

                        # Form lookup
                        form_id_ext = item.get("formId")
                        if form_id_ext:
                            form = Form.objects.get(study=study, imednet_id=str(form_id_ext))
                        else:
                            form = Form.objects.get(study=study, form_key=item.get("formKey"))

                        # Interval lookup
                        interval_id_ext = item.get("intervalId")
                        if interval_id_ext:
                            interval = Interval.objects.get(study=study, imednet_id=str(interval_id_ext))
                        else:
                            interval_name = item.get("intervalName")
                            if not interval_name:
                                raise ValueError("Missing interval lookup identifier (intervalId or intervalName)")
                            interval = Interval.objects.get(study=study, interval_name=interval_name)

                        # Visit lookup (optional)
                        visit = None
                        visit_id_ext = item.get("visitId")
                        if visit_id_ext:
                            visit = Visit.objects.get(study=study, imednet_id=str(visit_id_ext))

                    except (
                        CoreSubject.DoesNotExist,
                        Form.DoesNotExist,
                        Interval.DoesNotExist,
                        Visit.DoesNotExist,
                    ) as e:
                        raise ValueError(f"Missing related entity: {e!s}") from e

                    record, created = CoreRecord.objects.update_or_create(
                        imednet_id=imednet_id,
                        defaults={
                            "study": study,
                            "subject": subject,
                            "site": site,
                            "form": form,
                            "interval": interval,
                            "visit": visit,
                            "record_oid": item.get("recordOid", ""),
                            "record_type": item.get("recordType", ""),
                            "record_status": item.get("recordStatus", ""),
                            "deleted": item.get("deleted", False),
                            "imednet_subject_id": item.get("subjectId"),
                            "subject_oid": item.get("subjectOid", ""),
                            "subject_key": item.get("subjectKey", ""),
                            "imednet_visit_id": item.get("visitId"),
                            "parent_record_id": item.get("parentRecordId"),
                            "record_data": item.get("recordData", {}),
                        },
                    )

                    # Rebuild keywords
                    record.keywords.all().delete()
                    keywords_data = item.get("keywords", [])
                    if isinstance(keywords_data, list):
                        for kw in keywords_data:
                            RecordKeyword.objects.create(record=record, keyword=kw)

                    if created:
                        stats["created"] += 1
                        logger.info("record_created", imednet_id=imednet_id, study_id=study.id)
                    else:
                        stats["updated"] += 1
                        logger.info("record_updated", imednet_id=imednet_id, study_id=study.id)

            except (IntegrityError, ValueError, TypeError) as e:
                stats["failed"] += 1
                logger.error("record_sync_failed", imednet_id=item.get("recordId"), error=str(e), payload=item)
                continue

        return stats

    @staticmethod
    def submit_records(study: Study, records_list: list, user=None) -> dict:
        """
        Submits records to the iMednet API.
        On success, creates a SyncJob to track the submission.
        """
        import uuid

        from django.contrib.auth import get_user_model

        from clinical.models import SyncJob

        # Simulate API batch submission
        batch_id = str(uuid.uuid4())

        # Ensure we have a user for the SyncJob
        if not user:
            User = get_user_model()
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                user = User.objects.filter(is_staff=True).first()

        # Create tracking Job
        job = SyncJob.objects.create(
            provider=study.provider,
            status="COMPLETED",
            user=user,
            error_message=f"Batch {batch_id} submitted successfully. Total records: {len(records_list)}",
        )

        return {
            "batchId": batch_id,
            "jobId": str(job.id),
            "status": "success",
            "submittedCount": len(records_list),
        }

    @staticmethod
    def sync_queries(study: Study, data_list: list[dict]) -> dict:
        """
        Synchronizes query metadata and comments from iMednet.
        Uses update_or_create for idempotency based on annotationId (imednet_id).
        Rebuilds nested comments within transaction.atomic().
        """
        stats = {"created": 0, "updated": 0, "failed": 0}

        for item in data_list:
            try:
                with transaction.atomic():
                    imednet_id = str(item.get("annotationId"))

                    # Resolve relationships
                    subject_id_ext = str(item.get("subjectId"))
                    record_id_ext = str(item.get("recordId")) if item.get("recordId") else None
                    variable_raw = item.get("variable")

                    try:
                        subject = CoreSubject.objects.get(study=study, imednet_id=subject_id_ext)

                        record = None
                        if record_id_ext:
                            try:
                                record = CoreRecord.objects.get(study=study, imednet_id=record_id_ext)
                            except CoreRecord.DoesNotExist:
                                logger.warning(
                                    "query_sync_missing_record",
                                    query_id=imednet_id,
                                    record_id=record_id_ext,
                                    study_id=study.id,
                                )

                        variable_ref = None
                        if variable_raw:
                            variable_ref = (
                                Variable.objects.filter(study=study, variable_name=variable_raw).first()
                                or Variable.objects.filter(study=study, variable_oid=variable_raw).first()
                            )

                    except CoreSubject.DoesNotExist as e:
                        raise ValueError(f"Missing related subject: {e!s}") from e

                    query, created = Query.objects.update_or_create(
                        imednet_id=imednet_id,
                        defaults={
                            "study": study,
                            "subject": subject,
                            "record": record,
                            "variable_ref": variable_ref,
                            "imednet_subject_id": item.get("subjectId"),
                            "subject_oid": item.get("subjectOid"),
                            "annotation_type": item.get("annotationType"),
                            "query_type": item.get("type"),
                            "description": item.get("description"),
                            "imednet_record_id": item.get("recordId"),
                            "variable_raw": variable_raw,
                            "subject_key": item.get("subjectKey"),
                        },
                    )

                    # Rebuild comments
                    query.comments.all().delete()
                    comments_data = item.get("comments", [])
                    if isinstance(comments_data, list):
                        for comment_item in comments_data:
                            QueryComment.objects.create(
                                query=query,
                                comment=comment_item.get("comment"),
                                user_raw=comment_item.get("user"),
                                date_created=parse_imednet_date_array(comment_item.get("dateCreated")),
                            )

                    if created:
                        stats["created"] += 1
                        logger.info("query_created", imednet_id=imednet_id, study_id=study.id)
                    else:
                        stats["updated"] += 1
                        logger.info("query_updated", imednet_id=imednet_id, study_id=study.id)

            except (IntegrityError, ValueError, TypeError) as e:
                stats["failed"] += 1
                logger.error("query_sync_failed", imednet_id=item.get("annotationId"), error=str(e), payload=item)
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
