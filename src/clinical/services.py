from users.models import SiteMembership, StudyMembership
from django.db.models import Q
import logging

from celery import shared_task
from django.db import transaction

from clinical import models

from .adapter import MultiVendorAdapter

logger = logging.getLogger(__name__)

# Business logic for syncing entities


def sync_study(request, payload):
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "name": payload.name,
        "updated_by": request.user,
    }
    study, _ = models.Study.objects.update_or_create(
        external_id=payload.external_id, defaults=defaults, create_defaults={**defaults, "created_by": request.user}
    )
    check_and_process_orphans(study.external_id)
    return study


def sync_site(request, payload):
    study = get_accessible_studies(request).filter(external_id=payload.study_ext_id).first()
    if not study:
        models.BufferedOrphan.objects.create(
            entity_type="Site", missing_parent_id=payload.study_ext_id, payload=payload.dict(), user=request.user
        )
        return 202, {"message": "Buffered due to missing parent"}
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "study": study,
        "name": payload.name,
        "updated_by": request.user,
    }
    site, _ = models.Site.objects.update_or_create(
        external_id=payload.external_id, defaults=defaults, create_defaults={**defaults, "created_by": request.user}
    )
    check_and_process_orphans(site.external_id)
    return site


def sync_subject(request, payload):
    site = get_accessible_sites(request).filter(external_id=payload.site_ext_id).first()
    if not site:
        models.BufferedOrphan.objects.create(
            entity_type="Subject", missing_parent_id=payload.site_ext_id, payload=payload.dict(), user=request.user
        )
        return 202, {"message": "Buffered due to missing parent"}
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "site": site,
        "name": payload.name,
        "updated_by": request.user,
    }
    subject, _ = models.Subject.objects.update_or_create(
        external_id=payload.external_id, defaults=defaults, create_defaults={**defaults, "created_by": request.user}
    )
    check_and_process_orphans(subject.external_id)
    return subject


def sync_form(request, payload):
    study = get_accessible_studies(request).filter(external_id=payload.study_ext_id).first()
    if not study:
        models.BufferedOrphan.objects.create(
            entity_type="Form", missing_parent_id=payload.study_ext_id, payload=payload.dict(), user=request.user
        )
        return 202, {"message": "Buffered due to missing parent"}
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "study": study,
        "name": payload.name,
        "updated_by": request.user,
    }
    form, _ = models.Form.objects.update_or_create(
        external_id=payload.external_id, defaults=defaults, create_defaults={**defaults, "created_by": request.user}
    )
    check_and_process_orphans(form.external_id)
    return form


def sync_interval(request, payload):
    study = get_accessible_studies(request).filter(external_id=payload.study_ext_id).first()
    if not study:
        models.BufferedOrphan.objects.create(
            entity_type="Interval", missing_parent_id=payload.study_ext_id, payload=payload.dict(), user=request.user
        )
        return 202, {"message": "Buffered due to missing parent"}
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "study": study,
        "name": payload.name,
        "updated_by": request.user,
    }
    interval, _ = models.Interval.objects.update_or_create(
        external_id=payload.external_id, defaults=defaults, create_defaults={**defaults, "created_by": request.user}
    )
    check_and_process_orphans(interval.external_id)
    return interval


def sync_variable(request, payload):
    form = (
        models.Form.objects.filter(study__in=get_accessible_studies(request))
        .filter(external_id=payload.form_ext_id)
        .first()
    )
    if not form:
        models.BufferedOrphan.objects.create(
            entity_type="Variable", missing_parent_id=payload.form_ext_id, payload=payload.dict(), user=request.user
        )
        return 202, {"message": "Buffered due to missing parent"}
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "form": form,
        "name": payload.name,
        "updated_by": request.user,
    }
    variable, _ = models.Variable.objects.update_or_create(
        external_id=payload.external_id, defaults=defaults, create_defaults={**defaults, "created_by": request.user}
    )
    check_and_process_orphans(variable.external_id)
    return variable


def sync_visit(request, payload):
    subject = get_accessible_subjects(request).filter(external_id=payload.subject_ext_id).first()
    if not subject:
        models.BufferedOrphan.objects.create(
            entity_type="Visit", missing_parent_id=payload.subject_ext_id, payload=payload.dict(), user=request.user
        )
        return 202, {"message": "Buffered due to missing parent"}
    interval = (
        models.Interval.objects.filter(study__in=get_accessible_studies(request))
        .filter(external_id=payload.interval_ext_id)
        .first()
    )
    if not interval:
        models.BufferedOrphan.objects.create(
            entity_type="Visit", missing_parent_id=payload.interval_ext_id, payload=payload.dict(), user=request.user
        )
        return 202, {"message": "Buffered due to missing parent"}
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "subject": subject,
        "interval": interval,
        "updated_by": request.user,
    }
    visit, _ = models.Visit.objects.update_or_create(
        external_id=payload.external_id, defaults=defaults, create_defaults={**defaults, "created_by": request.user}
    )
    check_and_process_orphans(visit.external_id)
    return visit


def sync_record(request, payload):
    visit = (
        models.Visit.objects.filter(subject__in=get_accessible_subjects(request))
        .filter(external_id=payload.visit_ext_id)
        .first()
    )
    if not visit:
        models.BufferedOrphan.objects.create(
            entity_type="Record", missing_parent_id=payload.visit_ext_id, payload=payload.dict(), user=request.user
        )
        return 202, {"message": "Buffered due to missing parent"}
    variable = (
        models.Variable.objects.filter(form__study__in=get_accessible_studies(request))
        .filter(external_id=payload.variable_ext_id)
        .first()
    )
    if not variable:
        models.BufferedOrphan.objects.create(
            entity_type="Record", missing_parent_id=payload.variable_ext_id, payload=payload.dict(), user=request.user
        )
        return 202, {"message": "Buffered due to missing parent"}
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "visit": visit,
        "variable": variable,
        "value": payload.value,
        "updated_by": request.user,
    }
    record, _ = models.Record.objects.update_or_create(
        external_id=payload.external_id, defaults=defaults, create_defaults={**defaults, "created_by": request.user}
    )
    check_and_process_orphans(record.external_id)
    return record


def sync_coding(request, payload):
    record = (
        models.Record.objects.filter(visit__subject__in=get_accessible_subjects(request))
        .filter(external_id=payload.record_ext_id)
        .first()
    )
    if not record:
        models.BufferedOrphan.objects.create(
            entity_type="Coding", missing_parent_id=payload.record_ext_id, payload=payload.dict(), user=request.user
        )
        return 202, {"message": "Buffered due to missing parent"}
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "record": record,
        "code": payload.code,
        "updated_by": request.user,
    }
    coding, _ = models.Coding.objects.update_or_create(
        external_id=payload.external_id, defaults=defaults, create_defaults={**defaults, "created_by": request.user}
    )
    check_and_process_orphans(coding.external_id)
    return coding


def sync_query(request, payload):
    record = (
        models.Record.objects.filter(visit__subject__in=get_accessible_subjects(request))
        .filter(external_id=payload.record_ext_id)
        .first()
    )
    if not record:
        models.BufferedOrphan.objects.create(
            entity_type="Query", missing_parent_id=payload.record_ext_id, payload=payload.dict(), user=request.user
        )
        return 202, {"message": "Buffered due to missing parent"}

    query = models.Query.objects.filter(external_id=payload.external_id).first()

    if query:
        # Reconciliation logic
        if query.sync_status == "PENDING":
            if payload.status == query.status:
                # Upstream confirmed our optimistic state!
                query.sync_status = "CONFIRMED"
            else:
                # Replica is likely stale, don't overwrite optimistic status
                pass
        else:
            # Not pending, just accept replica's status
            query.status = payload.status or "OPEN"
            query.sync_status = "CONFIRMED"

        query.clinical_timestamp = payload.clinical_timestamp
        query.source_sequence = payload.source_sequence
        query.text = payload.text
        query.updated_by = request.user
        query.save()
    else:
        query = models.Query.objects.create(
            external_id=payload.external_id,
            record=record,
            clinical_timestamp=payload.clinical_timestamp,
            source_sequence=payload.source_sequence,
            text=payload.text,
            status=payload.status or "OPEN",
            sync_status="CONFIRMED",
            created_by=request.user,
            updated_by=request.user,
        )

    check_and_process_orphans(query.external_id)
    return query


def sync_revision(request, payload):
    record = (
        models.Record.objects.filter(visit__subject__in=get_accessible_subjects(request))
        .filter(external_id=payload.record_ext_id)
        .first()
    )
    if not record:
        models.BufferedOrphan.objects.create(
            entity_type="RecordRevision",
            missing_parent_id=payload.record_ext_id,
            payload=payload.dict(),
            user=request.user,
        )
        return 202, {"message": "Buffered due to missing parent"}
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "record": record,
        "value": payload.value,
        "updated_by": request.user,
    }
    revision, _ = models.RecordRevision.objects.update_or_create(
        external_id=payload.external_id, defaults=defaults, create_defaults={**defaults, "created_by": request.user}
    )
    check_and_process_orphans(revision.external_id)
    return revision


def check_and_process_orphans(parent_external_id):
    orphans = list(models.BufferedOrphan.objects.filter(missing_parent_id=parent_external_id))
    for orphan in orphans:
        try:
            with transaction.atomic():
                _reprocess_orphan(orphan)
        except Exception as e:
            logger.warning("Orphan reprocessing failed for parent %s: %s", parent_external_id, e)


def _reprocess_orphan(orphan):
    req = type("DummyRequest", (object,), {"user": orphan.user, "provider": orphan.provider, "user_roles": ["cdisc"]})()

    adapter = MultiVendorAdapter(orphan.provider)
    adapter.sync_entity(req, orphan.entity_type, orphan.payload)

    orphan.delete()


@shared_task
def reconstruct_subject_timeline(subject_id):
    try:
        subject = models.Subject.objects.get(id=subject_id)
    except models.Subject.DoesNotExist:
        return

    baseline = subject.baseline_date
    if not baseline:
        return

    # Update offset_days for all descendant entities
    models_to_update = [models.Visit, models.Record, models.Coding, models.Query, models.RecordRevision]
    for model in models_to_update:
        records_to_update = []
        if model == models.Visit:
            qs = model.objects.filter(subject=subject)
        elif model in [models.Record]:
            qs = model.objects.filter(visit__subject=subject)
        elif model in [models.Coding, models.Query, models.RecordRevision]:
            qs = model.objects.filter(record__visit__subject=subject)
        else:
            continue

        for obj in qs.filter(clinical_timestamp__isnull=False):
            new_offset = (obj.clinical_timestamp.date() - baseline.date()).days
            if obj.offset_days != new_offset:
                obj.offset_days = new_offset
                records_to_update.append(obj)

        if records_to_update:
            model.objects.bulk_update(records_to_update, ["offset_days"])

    # Update source_sequence if not set for models.Record
    records = models.Record.objects.filter(visit__subject=subject).order_by("clinical_timestamp", "created_at")
    records_to_update_seq = []
    for seq, rec in enumerate(records, start=1):
        if rec.source_sequence is None:
            rec.source_sequence = seq
            records_to_update_seq.append(rec)

    if records_to_update_seq:
        models.Record.objects.bulk_update(records_to_update_seq, ["source_sequence"])


def get_accessible_studies(request):

    user = request.user

    qs = models.Study.objects.all()
    if request.studyKey:
        qs = qs.filter(external_id=request.studyKey)
    elif request.siteKey:
        qs = qs.filter(sites__external_id=request.siteKey)

    if user.is_staff or user.is_superuser:
        return qs.distinct()

    auditor_study_ids = StudyMembership.objects.filter(user=user, role="clinical_auditor").values_list(
        "study_id", flat=True
    )
    investigator_study_ids = SiteMembership.objects.filter(user=user, role="site_investigator").values_list(
        "site__study_id", flat=True
    )
    return qs.filter(Q(id__in=auditor_study_ids) | Q(id__in=investigator_study_ids)).distinct()


def get_accessible_sites(request):

    user = request.user

    qs = models.Site.objects.all()
    if request.siteKey:
        qs = qs.filter(external_id=request.siteKey)
    if request.studyKey:
        qs = qs.filter(study__external_id=request.studyKey)

    if user.is_staff or user.is_superuser:
        return qs.distinct()

    auditor_study_ids = StudyMembership.objects.filter(user=user, role="clinical_auditor").values_list(
        "study_id", flat=True
    )
    investigator_site_ids = SiteMembership.objects.filter(user=user, role="site_investigator").values_list(
        "site_id", flat=True
    )
    return qs.filter(Q(study_id__in=auditor_study_ids) | Q(id__in=investigator_site_ids)).distinct()


def get_accessible_subjects(request):

    user = request.user

    qs = models.Subject.objects.all()
    if request.siteKey:
        qs = qs.filter(site__external_id=request.siteKey)
    if request.studyKey:
        qs = qs.filter(site__study__external_id=request.studyKey)

    if user.is_staff or user.is_superuser:
        return qs.distinct()

    auditor_study_ids = StudyMembership.objects.filter(user=user, role="clinical_auditor").values_list(
        "study_id", flat=True
    )
    investigator_site_ids = SiteMembership.objects.filter(user=user, role="site_investigator").values_list(
        "site_id", flat=True
    )
    return qs.filter(Q(site__study_id__in=auditor_study_ids) | Q(site_id__in=investigator_site_ids)).distinct()
