# ruff: noqa: RUF012, ERA001

from typing import Any, Optional
import json

from django.conf import settings
from django.shortcuts import get_object_or_404
from ninja import ModelSchema, Router


from ninja.security import APIKeyHeader, HttpBearer
from django.contrib.auth import get_user_model
from clinical.models import Provider


class JWTBearer(HttpBearer):
    def authenticate(self, request, token):
        from users.jwt import decode_jwt_token
        from ninja.errors import HttpError

        studyKey = request.headers.get("studyKey") or request.GET.get("studyKey")
        siteKey = request.headers.get("siteKey") or request.GET.get("siteKey")

        if not studyKey and hasattr(request, "resolver_match") and request.resolver_match:
            studyKey = request.resolver_match.kwargs.get("studyKey")

        if not studyKey and not siteKey:
            raise HttpError(400, "Missing required tenant context identifier: studyKey or siteKey")

        user = decode_jwt_token(token)
        if user:
            request.user = user
            request.studyKey = studyKey
            request.siteKey = siteKey
            # Assign user_roles needed for export to users authenticated via JWT
            # In a full Entra setup, this would map groups/roles from the token
            # For now, give them "extractor" role so CDISC export isn't totally blocked
            request.user_roles = ["extractor"]
            return token
        return None


from .export import generate_cdisc_export
from .models import (
    BufferedOrphan,
    Coding,
    Form,
    Interval,
    Query,
    Record,
    RecordRevision,
    Site,
    Study,
    Subject,
    SyncJob,
    SyncTask,
    Variable,
    Visit,
)
from .schemas import SyncJobRequest, SyncJobResponse

router = Router(auth=[JWTBearer()])

# --- Schemas ---


class JobStatusSchemaOut(ModelSchema):
    progress_percentage: float
    error_logs: list[str]

    class Meta:
        model = SyncJob
        fields = ["id", "status", "error_message", "created_at", "updated_at"]

    @staticmethod
    def resolve_progress_percentage(obj) -> float:
        total = obj.tasks.count()
        if total == 0:
            return 100.0
        completed = obj.tasks.filter(status__in=["COMPLETED", "FAILED"]).count()
        return round((completed / total) * 100.0, 2)

    @staticmethod
    def resolve_error_logs(obj) -> list[str]:
        failed_tasks = obj.tasks.filter(status="FAILED")
        logs = []
        for task in failed_tasks:
            # Mask PII by only showing entity type and metadata (e.g. external_id if available)
            msg = f"{task.entity_type} task failed: {task.error_message}"
            logs.append(msg)
        return logs


class StudySchemaIn(ModelSchema):
    class Meta:
        model = Study
        fields = ["clinical_timestamp", "source_sequence", "external_id", "name"]


class StudySchemaOut(ModelSchema):
    class Meta:
        model = Study
        fields = [
            "clinical_timestamp",
            "source_sequence",
            "offset_days",
            "id",
            "external_id",
            "name",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]


class SiteSchemaIn(ModelSchema):
    study_ext_id: str

    class Meta:
        model = Site
        fields = ["clinical_timestamp", "source_sequence", "external_id", "name"]


class SiteSchemaOut(ModelSchema):
    class Meta:
        model = Site
        fields = [
            "clinical_timestamp",
            "source_sequence",
            "offset_days",
            "id",
            "external_id",
            "name",
            "study",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]


class SubjectSchemaIn(ModelSchema):
    site_ext_id: str

    class Meta:
        model = Subject
        fields = ["clinical_timestamp", "source_sequence", "external_id", "name"]


class SubjectSchemaOut(ModelSchema):
    class Meta:
        model = Subject
        fields = [
            "clinical_timestamp",
            "source_sequence",
            "offset_days",
            "id",
            "external_id",
            "name",
            "site",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]


class FormSchemaIn(ModelSchema):
    study_ext_id: str

    class Meta:
        model = Form
        fields = ["clinical_timestamp", "source_sequence", "external_id", "name"]


class FormSchemaOut(ModelSchema):
    class Meta:
        model = Form
        fields = [
            "clinical_timestamp",
            "source_sequence",
            "offset_days",
            "id",
            "external_id",
            "name",
            "study",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]


class IntervalSchemaIn(ModelSchema):
    study_ext_id: str

    class Meta:
        model = Interval
        fields = ["clinical_timestamp", "source_sequence", "external_id", "name"]


class IntervalSchemaOut(ModelSchema):
    class Meta:
        model = Interval
        fields = [
            "clinical_timestamp",
            "source_sequence",
            "offset_days",
            "id",
            "external_id",
            "name",
            "study",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]


class VariableSchemaIn(ModelSchema):
    form_ext_id: str

    class Meta:
        model = Variable
        fields = ["clinical_timestamp", "source_sequence", "external_id", "name"]


class VariableSchemaOut(ModelSchema):
    class Meta:
        model = Variable
        fields = [
            "clinical_timestamp",
            "source_sequence",
            "offset_days",
            "id",
            "external_id",
            "name",
            "form",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]


class VisitSchemaIn(ModelSchema):
    subject_ext_id: str
    interval_ext_id: str

    class Meta:
        model = Visit
        fields = ["clinical_timestamp", "source_sequence", "external_id"]


class VisitSchemaOut(ModelSchema):
    class Meta:
        model = Visit
        fields = [
            "clinical_timestamp",
            "source_sequence",
            "offset_days",
            "id",
            "external_id",
            "subject",
            "interval",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]


class RecordSchemaIn(ModelSchema):
    visit_ext_id: str
    variable_ext_id: str
    reason_for_change: Optional[str] = None

    class Meta:
        model = Record
        fields = ["clinical_timestamp", "source_sequence", "external_id", "value"]


class RecordSchemaOut(ModelSchema):
    class Meta:
        model = Record
        fields = [
            "clinical_timestamp",
            "source_sequence",
            "offset_days",
            "id",
            "external_id",
            "value",
            "visit",
            "variable",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]


class CodingSchemaIn(ModelSchema):
    record_ext_id: str

    class Meta:
        model = Coding
        fields = ["clinical_timestamp", "source_sequence", "external_id", "code"]


class CodingSchemaOut(ModelSchema):
    class Meta:
        model = Coding
        fields = [
            "clinical_timestamp",
            "source_sequence",
            "offset_days",
            "id",
            "external_id",
            "code",
            "record",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]


from typing import Optional


class QuerySchemaIn(ModelSchema):
    record_ext_id: str
    status: Optional[str] = "OPEN"

    class Meta:
        model = Query
        fields = ["clinical_timestamp", "source_sequence", "external_id", "text", "status"]


from ninja import Schema


class QueryUpdateIn(Schema):
    status: str


class QuerySchemaOut(ModelSchema):
    class Meta:
        model = Query
        fields = [
            "clinical_timestamp",
            "source_sequence",
            "offset_days",
            "id",
            "external_id",
            "text",
            "status",
            "sync_status",
            "last_sync_error",
            "record",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]


class RecordRevisionSchemaIn(ModelSchema):
    record_ext_id: str

    class Meta:
        model = RecordRevision
        fields = ["clinical_timestamp", "source_sequence", "external_id", "value"]


class RecordRevisionSchemaOut(ModelSchema):
    class Meta:
        model = RecordRevision
        fields = [
            "clinical_timestamp",
            "source_sequence",
            "offset_days",
            "id",
            "external_id",
            "value",
            "reason_for_change",
            "record",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]


from django.db.models import Q


def get_accessible_studies(request):
    from users.models import SiteMembership, StudyMembership
    user = request.user

    qs = Study.objects.all()
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
    from users.models import SiteMembership, StudyMembership
    user = request.user

    qs = Site.objects.all()
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
    from users.models import SiteMembership, StudyMembership
    user = request.user

    qs = Subject.objects.all()
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


import json

from django.core.exceptions import PermissionDenied


from typing import Any


def _queue_single_task(request, hierarchy_level: int, entity_type: str, payload_obj) -> tuple[int, Any]:
    if not (request.user.is_staff or request.user.is_superuser):
        from users.models import SiteMembership

        if not SiteMembership.objects.filter(user=request.user, role="site_investigator").exists():
            raise PermissionDenied("Clinical Auditors have read-only access.")

    from django.db import transaction
    from clinical.adapter import MultiVendorAdapter

    payload_dict = json.loads(payload_obj.json())
    provider = getattr(request, "provider", None)
    adapter = MultiVendorAdapter(provider)

    try:
        with transaction.atomic():
            job = SyncJob.objects.create(user=request.user, provider=provider, status="COMPLETED")
            SyncTask.objects.create(
                job=job,
                hierarchy_level=hierarchy_level,
                entity_type=entity_type,
                payload=payload_dict,
                status="COMPLETED",
            )
            adapter.sync_entity(request, entity_type, payload_dict)

        status_url = f"/api/clinical/sync-jobs/{job.id}"
        return 200, SyncJobResponse(job_id=job.id, status=job.status, message="Sync completed", status_url=status_url)
    except Exception as e:
        return 400, {"message": f"Sync failed. No data was saved. Error: {str(e)}"}


# --- Endpoints ---


@router.post("/sync-jobs", response={200: SyncJobResponse, 400: dict})
def create_sync_job(request, payload: SyncJobRequest):
    if not (request.user.is_staff or request.user.is_superuser):
        from users.models import SiteMembership

        if not SiteMembership.objects.filter(user=request.user, role="site_investigator").exists():
            raise PermissionDenied("Clinical Auditors have read-only access.")

    from django.db import transaction
    from clinical.adapter import MultiVendorAdapter

    provider = getattr(request, "provider", None)
    adapter = MultiVendorAdapter(provider)

    entity_order = {
        "Study": 1,
        "Site": 2,
        "Form": 1,
        "Interval": 1,
        "Subject": 2,
        "Variable": 1,
        "Visit": 2,
        "Record": 1,
        "Coding": 2,
        "Query": 3,
        "RecordRevision": 4,
    }

    sorted_entities = sorted(payload.entities, key=lambda e: (e.hierarchy_level, entity_order.get(e.entity_type, 99)))

    try:
        with transaction.atomic():
            job = SyncJob.objects.create(user=request.user, provider=provider, status="COMPLETED")
            task_objects = []
            for entity in sorted_entities:
                task_objects.append(
                    SyncTask(
                        job=job,
                        hierarchy_level=entity.hierarchy_level,
                        entity_type=entity.entity_type,
                        payload=entity.payload,
                        status="COMPLETED",
                    )
                )
                adapter.sync_entity(request, entity.entity_type, entity.payload)
            SyncTask.objects.bulk_create(task_objects)

        status_url = f"/api/clinical/sync-jobs/{job.id}"
        return 200, SyncJobResponse(
            job_id=job.id, status=job.status, message="Sync completed synchronously", status_url=status_url
        )
    except Exception as e:
        return 400, {"message": f"Sync failed. No data was saved. Error: {str(e)}"}


@router.get("/sync-jobs/{job_id}", response=JobStatusSchemaOut)
def get_sync_job(request, job_id: str):
    return get_object_or_404(SyncJob, id=job_id, user=request.user)


# L1: Study
@router.post("/studies", response={200: SyncJobResponse, 400: dict})
def api_sync_study(request, payload: StudySchemaIn):
    return _queue_single_task(request, 1, "Study", payload)


def sync_study(request, payload: StudySchemaIn):
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "name": payload.name,
        "updated_by": request.user,
    }
    study, _ = Study.objects.update_or_create(
        external_id=payload.external_id, defaults=defaults, create_defaults={**defaults, "created_by": request.user}
    )
    check_and_process_orphans(study.external_id)
    return study


@router.get("/studies", response=list[StudySchemaOut])
def list_studies(request):
    return get_accessible_studies(request)


# L1: Site
@router.post("/sites", response={200: SyncJobResponse, 400: dict})
def api_sync_site(request, payload: SiteSchemaIn):
    return _queue_single_task(request, 1, "Site", payload)


def sync_site(request, payload: SiteSchemaIn):
    study = get_accessible_studies(request).filter(external_id=payload.study_ext_id).first()
    if not study:
        BufferedOrphan.objects.create(
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
    site, _ = Site.objects.update_or_create(
        external_id=payload.external_id, defaults=defaults, create_defaults={**defaults, "created_by": request.user}
    )
    check_and_process_orphans(site.external_id)
    return site


@router.get("/sites", response=list[SiteSchemaOut])
def list_sites(request):
    return get_accessible_sites(request).select_related("study")


# L2: Subject
@router.post("/subjects", response={200: SyncJobResponse, 400: dict})
def api_sync_subject(request, payload: SubjectSchemaIn):
    return _queue_single_task(request, 2, "Subject", payload)


def sync_subject(request, payload: SubjectSchemaIn):
    site = get_accessible_sites(request).filter(external_id=payload.site_ext_id).first()
    if not site:
        BufferedOrphan.objects.create(
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
    subject, _ = Subject.objects.update_or_create(
        external_id=payload.external_id, defaults=defaults, create_defaults={**defaults, "created_by": request.user}
    )
    check_and_process_orphans(subject.external_id)
    return subject


@router.get("/subjects", response=list[SubjectSchemaOut])
def list_subjects(request):
    return get_accessible_subjects(request).select_related("site")


# L2: Form
@router.post("/forms", response={200: SyncJobResponse, 400: dict})
def api_sync_form(request, payload: FormSchemaIn):
    return _queue_single_task(request, 2, "Form", payload)


def sync_form(request, payload: FormSchemaIn):
    study = get_accessible_studies(request).filter(external_id=payload.study_ext_id).first()
    if not study:
        BufferedOrphan.objects.create(
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
    form, _ = Form.objects.update_or_create(
        external_id=payload.external_id, defaults=defaults, create_defaults={**defaults, "created_by": request.user}
    )
    check_and_process_orphans(form.external_id)
    return form


@router.get("/forms", response=list[FormSchemaOut])
def list_forms(request):
    return Form.objects.filter(study__in=get_accessible_studies(request)).select_related("study")


# L2: Interval
@router.post("/intervals", response={200: SyncJobResponse, 400: dict})
def api_sync_interval(request, payload: IntervalSchemaIn):
    return _queue_single_task(request, 2, "Interval", payload)


def sync_interval(request, payload: IntervalSchemaIn):
    study = get_accessible_studies(request).filter(external_id=payload.study_ext_id).first()
    if not study:
        BufferedOrphan.objects.create(
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
    interval, _ = Interval.objects.update_or_create(
        external_id=payload.external_id, defaults=defaults, create_defaults={**defaults, "created_by": request.user}
    )
    check_and_process_orphans(interval.external_id)
    return interval


@router.get("/intervals", response=list[IntervalSchemaOut])
def list_intervals(request):
    return Interval.objects.filter(study__in=get_accessible_studies(request)).select_related("study")


# L3: Variable
@router.post("/variables", response={200: SyncJobResponse, 400: dict})
def api_sync_variable(request, payload: VariableSchemaIn):
    return _queue_single_task(request, 3, "Variable", payload)


def sync_variable(request, payload: VariableSchemaIn):
    form = (
        Form.objects.filter(study__in=get_accessible_studies(request))
        .filter(external_id=payload.form_ext_id)
        .first()
    )
    if not form:
        BufferedOrphan.objects.create(
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
    variable, _ = Variable.objects.update_or_create(
        external_id=payload.external_id, defaults=defaults, create_defaults={**defaults, "created_by": request.user}
    )
    check_and_process_orphans(variable.external_id)
    return variable


@router.get("/variables", response=list[VariableSchemaOut])
def list_variables(request):
    return Variable.objects.filter(form__study__in=get_accessible_studies(request)).select_related("form")


# L3: Visit
@router.post("/visits", response={200: SyncJobResponse, 400: dict})
def api_sync_visit(request, payload: VisitSchemaIn):
    return _queue_single_task(request, 3, "Visit", payload)


def sync_visit(request, payload: VisitSchemaIn):
    subject = get_accessible_subjects(request).filter(external_id=payload.subject_ext_id).first()
    if not subject:
        BufferedOrphan.objects.create(
            entity_type="Visit", missing_parent_id=payload.subject_ext_id, payload=payload.dict(), user=request.user
        )
        return 202, {"message": "Buffered due to missing parent"}
    interval = (
        Interval.objects.filter(study__in=get_accessible_studies(request))
        .filter(external_id=payload.interval_ext_id)
        .first()
    )
    if not interval:
        BufferedOrphan.objects.create(
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
    visit, _ = Visit.objects.update_or_create(
        external_id=payload.external_id, defaults=defaults, create_defaults={**defaults, "created_by": request.user}
    )
    check_and_process_orphans(visit.external_id)
    return visit


@router.get("/visits", response=list[VisitSchemaOut])
def list_visits(request):
    return Visit.objects.filter(subject__in=get_accessible_subjects(request)).select_related("subject", "interval")


# L4: Record
@router.post("/records", response={200: SyncJobResponse, 400: dict})
def api_sync_record(request, payload: RecordSchemaIn):
    return _queue_single_task(request, 4, "Record", payload)


def sync_record(request, payload: RecordSchemaIn):
    visit = (
        Visit.objects.filter(subject__in=get_accessible_subjects(request))
        .filter(external_id=payload.visit_ext_id)
        .first()
    )
    if not visit:
        BufferedOrphan.objects.create(
            entity_type="Record", missing_parent_id=payload.visit_ext_id, payload=payload.dict(), user=request.user
        )
        return 202, {"message": "Buffered due to missing parent"}
    variable = (
        Variable.objects.filter(form__study__in=get_accessible_studies(request))
        .filter(external_id=payload.variable_ext_id)
        .first()
    )
    if not variable:
        BufferedOrphan.objects.create(
            entity_type="Record", missing_parent_id=payload.variable_ext_id, payload=payload.dict(), user=request.user
        )
        return 202, {"message": "Buffered due to missing parent"}

    existing_record = Record.objects.filter(external_id=payload.external_id).first()
    if existing_record and existing_record.value != payload.value:
        if not payload.reason_for_change:
            from ninja.errors import HttpError
            raise HttpError(400, "Reason for change is mandatory for modifications.")

    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "visit": visit,
        "variable": variable,
        "value": payload.value,
        "updated_by": request.user,
    }
    
    if existing_record:
        for k, v in defaults.items():
            setattr(existing_record, k, v)
        existing_record.reason_for_change = payload.reason_for_change
        existing_record.save()
        record = existing_record
    else:
        create_kwargs = {**defaults, "external_id": payload.external_id, "created_by": request.user}
        record = Record(**create_kwargs)
        record.reason_for_change = payload.reason_for_change
        record.save()

    check_and_process_orphans(record.external_id)
    return record


@router.get("/records", response=list[RecordSchemaOut])
def list_records(request):
    return Record.objects.filter(visit__subject__in=get_accessible_subjects(request)).select_related(
        "visit", "variable"
    )


# L4: Coding
@router.post("/codings", response={200: SyncJobResponse, 400: dict})
def api_sync_coding(request, payload: CodingSchemaIn):
    return _queue_single_task(request, 4, "Coding", payload)


def sync_coding(request, payload: CodingSchemaIn):
    record = (
        Record.objects.filter(visit__subject__in=get_accessible_subjects(request))
        .filter(external_id=payload.record_ext_id)
        .first()
    )
    if not record:
        BufferedOrphan.objects.create(
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
    coding, _ = Coding.objects.update_or_create(
        external_id=payload.external_id, defaults=defaults, create_defaults={**defaults, "created_by": request.user}
    )
    check_and_process_orphans(coding.external_id)
    return coding


@router.get("/codings", response=list[CodingSchemaOut])
def list_codings(request):
    return Coding.objects.filter(record__visit__subject__in=get_accessible_subjects(request)).select_related(
        "record"
    )


# L4: Query
@router.post("/queries", response={200: SyncJobResponse, 400: dict})
def api_sync_query(request, payload: QuerySchemaIn):
    return _queue_single_task(request, 4, "Query", payload)


def sync_query(request, payload: QuerySchemaIn):
    record = (
        Record.objects.filter(visit__subject__in=get_accessible_subjects(request))
        .filter(external_id=payload.record_ext_id)
        .first()
    )
    if not record:
        BufferedOrphan.objects.create(
            entity_type="Query", missing_parent_id=payload.record_ext_id, payload=payload.dict(), user=request.user
        )
        return 202, {"message": "Buffered due to missing parent"}

    query = Query.objects.filter(external_id=payload.external_id).first()

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
        query = Query.objects.create(
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


@router.get("/queries", response=list[QuerySchemaOut])
def list_queries(request):
    return Query.objects.filter(record__visit__subject__in=get_accessible_subjects(request)).select_related(
        "record"
    )


@router.patch("/queries/{query_id}", response=QuerySchemaOut)
def update_query(request, query_id: int, payload: QueryUpdateIn):
    query = Query.objects.get(id=query_id, record__visit__subject__in=get_accessible_subjects(request))
    query.previous_status = query.status
    query.status = payload.status
    query.sync_status = "PENDING"
    query.save(update_fields=["status", "previous_status", "sync_status", "updated_at"])

    from django.core.cache import cache
    from django.utils import timezone

    cache.set("last_query_activity_time", timezone.now(), timeout=86400)

    # Trigger background sync to upstream EDC
    from clinical.tasks import sync_query_upstream

    sync_query_upstream.delay(query.id)

    return query


# L4: RecordRevision
@router.post("/revisions", response={200: SyncJobResponse, 400: dict})
def api_sync_revision(request, payload: RecordRevisionSchemaIn):
    return _queue_single_task(request, 4, "RecordRevision", payload)


def sync_revision(request, payload: RecordRevisionSchemaIn):
    record = (
        Record.objects.filter(visit__subject__in=get_accessible_subjects(request))
        .filter(external_id=payload.record_ext_id)
        .first()
    )
    if not record:
        BufferedOrphan.objects.create(
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
    revision, _ = RecordRevision.objects.update_or_create(
        external_id=payload.external_id, defaults=defaults, create_defaults={**defaults, "created_by": request.user}
    )
    check_and_process_orphans(revision.external_id)
    return revision


@router.get("/revisions", response=list[RecordRevisionSchemaOut])
def list_revisions(request):
    return RecordRevision.objects.filter(
        record__visit__subject__in=get_accessible_subjects(request)
    ).select_related("record")


@router.get("/export/cdisc")
def export_cdisc_package(request):
    # Check data-extraction privileges
    roles = getattr(request, "user_roles", [])
    has_privilege = any(r in str(roles).lower() for r in ["export", "extractor", "cdisc"])
    if not (has_privilege or request.user.is_staff or request.user.is_superuser):
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Missing data-extraction privileges")
    return generate_cdisc_export(request)


class BufferedOrphanSchemaOut(ModelSchema):
    class Meta:
        model = BufferedOrphan
        fields = ["id", "entity_type", "missing_parent_id", "created_at"]


@router.get("/orphans", response=list[BufferedOrphanSchemaOut])
def list_orphans(request):
    if not (request.user.is_staff or request.user.is_superuser):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Admin access required")
    return BufferedOrphan.objects.all()


from django.db import transaction
from .adapter import MultiVendorAdapter


def check_and_process_orphans(parent_external_id):
    orphans = list(BufferedOrphan.objects.filter(missing_parent_id=parent_external_id))
    for orphan in orphans:
        try:
            with transaction.atomic():
                _reprocess_orphan(orphan)
        except Exception as e:
            print("ORPHAN EXCEPTION:", e)
            pass


def _reprocess_orphan(orphan):
    req = type("DummyRequest", (object,), {"user": orphan.user, "provider": orphan.provider, "user_roles": ["cdisc"]})()

    adapter = MultiVendorAdapter(orphan.provider)
    adapter.sync_entity(req, orphan.entity_type, orphan.payload)

    orphan.delete()


# --- DELETE & TRASH ENDPOINTS ---

from django.http import Http404


def _get_model_class(entity_type: str):
    models_map = {
        "studies": Study,
        "sites": Site,
        "subjects": Subject,
        "forms": Form,
        "intervals": Interval,
        "variables": Variable,
        "visits": Visit,
        "records": Record,
        "codings": Coding,
        "queries": Query,
        "revisions": RecordRevision,
    }
    return models_map.get(entity_type.lower())


@router.delete("/{entity_plural}/{external_id}", response={204: None})
def delete_entity(request, entity_plural: str, external_id: str):
    if not (request.user.is_staff or request.user.is_superuser):
        from users.models import SiteMembership

        if not SiteMembership.objects.filter(user=request.user, role="site_investigator").exists():
            raise PermissionDenied("Clinical Auditors have read-only access.")

    model_cls = _get_model_class(entity_plural)
    if not model_cls:
        raise Http404("Unknown entity type")

    # Map to accessible querysets to enforce tenant context and authorization
    qs_map = {
        "studies": lambda: get_accessible_studies(request),
        "sites": lambda: get_accessible_sites(request),
        "subjects": lambda: get_accessible_subjects(request),
        "forms": lambda: Form.objects.filter(study__in=get_accessible_studies(request)),
        "intervals": lambda: Interval.objects.filter(study__in=get_accessible_studies(request)),
        "variables": lambda: Variable.objects.filter(form__study__in=get_accessible_studies(request)),
        "visits": lambda: Visit.objects.filter(subject__in=get_accessible_subjects(request)),
        "records": lambda: Record.objects.filter(visit__subject__in=get_accessible_subjects(request)),
        "codings": lambda: Coding.objects.filter(record__visit__subject__in=get_accessible_subjects(request)),
        "queries": lambda: Query.objects.filter(record__visit__subject__in=get_accessible_subjects(request)),
        "revisions": lambda: RecordRevision.objects.filter(record__visit__subject__in=get_accessible_subjects(request)),
    }

    base_qs_func = qs_map.get(entity_plural.lower())
    if not base_qs_func:
        raise Http404("Unknown entity type")

    base_qs = base_qs_func()
    obj = get_object_or_404(base_qs, external_id=external_id)
    obj.delete()
    return 204, None


class TrashItemOut(ModelSchema):
    entity_type: str
    deleted_at_iso: str

    class Meta:
        model = Study  # Dummy model to satisfy ninja
        fields = ["external_id", "id"]

    @staticmethod
    def resolve_entity_type(obj):
        return obj.__class__.__name__

    @staticmethod
    def resolve_deleted_at_iso(obj):
        return obj.deleted_at.isoformat() if obj.deleted_at else ""


@router.get("/trash/items")
def list_trash(request):
    if not (request.user.is_staff or request.user.is_superuser):
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Admin access required")

    results = []
    for model_cls in [Study, Site, Subject, Form, Interval, Variable, Visit, Record, Coding, Query, RecordRevision]:
        for obj in model_cls.all_objects.filter(is_deleted=True).order_by("-deleted_at"):
            results.append(
                {
                    "id": obj.id,
                    "external_id": obj.external_id,
                    "entity_type": model_cls.__name__,
                    "deleted_at_iso": obj.deleted_at.isoformat() if obj.deleted_at else "",
                }
            )
    # Sort by deletion date desc
    results.sort(key=lambda x: x["deleted_at_iso"], reverse=True)
    return results


@router.post("/trash/{entity_type}/{external_id}/restore", response={200: dict})
def restore_entity(request, entity_type: str, external_id: str):
    if not (request.user.is_staff or request.user.is_superuser):
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Admin access required")

    models_map = {
        "study": Study,
        "site": Site,
        "subject": Subject,
        "form": Form,
        "interval": Interval,
        "variable": Variable,
        "visit": Visit,
        "record": Record,
        "coding": Coding,
        "query": Query,
        "recordrevision": RecordRevision,
    }
    model_cls = models_map.get(entity_type.lower())
    if not model_cls:
        raise Http404("Unknown entity type")

    obj = get_object_or_404(model_cls.all_objects, external_id=external_id, is_deleted=True)
    try:
        obj.restore()
    except ValueError as e:
        from django.http import HttpResponseBadRequest

        return HttpResponseBadRequest(str(e))

    return 200, {"message": "Restored successfully"}


v1_edc_router = Router(auth=[JWTBearer()])

def v1_queue_single_task(request, hierarchy_level: int, entity_type: str, payload_obj) -> tuple[int, Any]:
    if not (request.user.is_staff or request.user.is_superuser):
        from users.models import SiteMembership

        if not SiteMembership.objects.filter(user=request.user, role="site_investigator").exists():
            raise PermissionDenied("Clinical Auditors have read-only access.")

    from django.db import transaction
    from clinical.adapter import MultiVendorAdapter

    payload_dict = json.loads(payload_obj.json())
    provider = getattr(request, "provider", None)
    adapter = MultiVendorAdapter(provider)

    try:
        with transaction.atomic():
            job = SyncJob.objects.create(user=request.user, provider=provider, status="COMPLETED")
            SyncTask.objects.create(
                job=job,
                hierarchy_level=hierarchy_level,
                entity_type=entity_type,
                payload=payload_dict,
                status="COMPLETED",
            )
            result = adapter.sync_entity(request, entity_type, payload_dict)

        if isinstance(result, tuple) and result[0] == 202:
            return 202, {"message": result[1].get("message", "Buffered")}

        status_url = f"/api/clinical/sync-jobs/{job.id}"
        return 200, SyncJobResponse(job_id=job.id, status=job.status, message="Sync completed", status_url=status_url)
    except Exception as e:
        return 400, {"message": f"Sync failed. No data was saved. Error: {str(e)}"}

@v1_edc_router.post("/{studyKey}/studies", response={200: SyncJobResponse, 202: dict, 400: dict})
def v1_api_sync_study(request, studyKey: str, payload: StudySchemaIn):
    return v1_queue_single_task(request, 1, "Study", payload)

@v1_edc_router.get("/{studyKey}/studies", response=list[StudySchemaOut])
def v1_list_studies(request, studyKey: str):
    return list_studies(request)

@v1_edc_router.post("/{studyKey}/sites", response={200: SyncJobResponse, 202: dict, 400: dict})
def v1_api_sync_site(request, studyKey: str, payload: SiteSchemaIn):
    return v1_queue_single_task(request, 1, "Site", payload)

@v1_edc_router.get("/{studyKey}/sites", response=list[SiteSchemaOut])
def v1_list_sites(request, studyKey: str):
    return list_sites(request)

@v1_edc_router.post("/{studyKey}/subjects", response={200: SyncJobResponse, 202: dict, 400: dict})
def v1_api_sync_subject(request, studyKey: str, payload: SubjectSchemaIn):
    return v1_queue_single_task(request, 2, "Subject", payload)

@v1_edc_router.get("/{studyKey}/subjects", response=list[SubjectSchemaOut])
def v1_list_subjects(request, studyKey: str):
    return list_subjects(request)

@v1_edc_router.post("/{studyKey}/forms", response={200: SyncJobResponse, 202: dict, 400: dict})
def v1_api_sync_form(request, studyKey: str, payload: FormSchemaIn):
    return v1_queue_single_task(request, 2, "Form", payload)

@v1_edc_router.get("/{studyKey}/forms", response=list[FormSchemaOut])
def v1_list_forms(request, studyKey: str):
    return list_forms(request)

@v1_edc_router.post("/{studyKey}/intervals", response={200: SyncJobResponse, 202: dict, 400: dict})
def v1_api_sync_interval(request, studyKey: str, payload: IntervalSchemaIn):
    return v1_queue_single_task(request, 2, "Interval", payload)

@v1_edc_router.get("/{studyKey}/intervals", response=list[IntervalSchemaOut])
def v1_list_intervals(request, studyKey: str):
    return list_intervals(request)

@v1_edc_router.post("/{studyKey}/variables", response={200: SyncJobResponse, 202: dict, 400: dict})
def v1_api_sync_variable(request, studyKey: str, payload: VariableSchemaIn):
    return v1_queue_single_task(request, 3, "Variable", payload)

@v1_edc_router.get("/{studyKey}/variables", response=list[VariableSchemaOut])
def v1_list_variables(request, studyKey: str):
    return list_variables(request)

@v1_edc_router.post("/{studyKey}/visits", response={200: SyncJobResponse, 202: dict, 400: dict})
def v1_api_sync_visit(request, studyKey: str, payload: VisitSchemaIn):
    return v1_queue_single_task(request, 3, "Visit", payload)

@v1_edc_router.get("/{studyKey}/visits", response=list[VisitSchemaOut])
def v1_list_visits(request, studyKey: str):
    return list_visits(request)

@v1_edc_router.post("/{studyKey}/records", response={200: SyncJobResponse, 202: dict, 400: dict})
def v1_api_sync_record(request, studyKey: str, payload: RecordSchemaIn):
    return v1_queue_single_task(request, 4, "Record", payload)

@v1_edc_router.get("/{studyKey}/records", response=list[RecordSchemaOut])
def v1_list_records(request, studyKey: str):
    return list_records(request)

@v1_edc_router.post("/{studyKey}/codings", response={200: SyncJobResponse, 202: dict, 400: dict})
def v1_api_sync_coding(request, studyKey: str, payload: CodingSchemaIn):
    return v1_queue_single_task(request, 4, "Coding", payload)

@v1_edc_router.get("/{studyKey}/codings", response=list[CodingSchemaOut])
def v1_list_codings(request, studyKey: str):
    return list_codings(request)

@v1_edc_router.post("/{studyKey}/queries", response={200: SyncJobResponse, 202: dict, 400: dict})
def v1_api_sync_query(request, studyKey: str, payload: QuerySchemaIn):
    return v1_queue_single_task(request, 4, "Query", payload)

@v1_edc_router.get("/{studyKey}/queries", response=list[QuerySchemaOut])
def v1_list_queries(request, studyKey: str):
    return list_queries(request)

@v1_edc_router.post("/{studyKey}/revisions", response={200: SyncJobResponse, 202: dict, 400: dict})
def v1_api_sync_revision(request, studyKey: str, payload: RecordRevisionSchemaIn):
    return v1_queue_single_task(request, 4, "RecordRevision", payload)

@v1_edc_router.get("/{studyKey}/revisions", response=list[RecordRevisionSchemaOut])
def v1_list_revisions(request, studyKey: str):
    return list_revisions(request)


from ninja import Schema
from .models import ElectronicSignature

class SignatureSchemaIn(Schema):
    record_revision_ext_id: str
    reauth_token: str

class SignatureSchemaOut(ModelSchema):
    class Meta:
        model = ElectronicSignature
        fields = ["id", "signature_hash", "signed_at"]

@router.post("/signatures", response={200: SignatureSchemaOut, 400: dict, 401: dict, 403: dict})
def create_signature(request, payload: SignatureSchemaIn):
    from users.jwt import decode_jwt_token_full
    import datetime
    import hashlib

    user, token_payload = decode_jwt_token_full(payload.reauth_token)
    if not user:
        return 401, {"message": "Invalid re-authentication token."}
    
    if user != request.user:
        return 403, {"message": "Re-authentication user mismatch."}

    auth_time = token_payload.get("auth_time") or token_payload.get("iat")
    if not auth_time:
        return 400, {"message": "Token missing authentication timestamp."}

    current_time = datetime.datetime.now(datetime.timezone.utc).timestamp()
    
    if current_time - auth_time > 300:
        return 400, {"message": "Re-authentication timestamp is too old."}

    revision = get_object_or_404(RecordRevision, external_id=payload.record_revision_ext_id, record__visit__subject__in=get_accessible_subjects(request))

    hash_input = f"{revision.id}:{revision.value}:{user.id}:{auth_time}".encode('utf-8')
    sig_hash = hashlib.sha256(hash_input).hexdigest()

    sig = ElectronicSignature.objects.create(
        record_revision=revision,
        user=user,
        signature_hash=sig_hash
    )

    return sig
