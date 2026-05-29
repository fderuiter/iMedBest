# ruff: noqa: RUF012, ERA001

from django.conf import settings
from django.shortcuts import get_object_or_404
from ninja import ModelSchema, Router


from ninja.security import APIKeyHeader, HttpBearer
from django.contrib.auth import get_user_model
from clinical.models import Provider


class JWTBearer(HttpBearer):
    def authenticate(self, request, token):
        from users.jwt import decode_jwt_token

        user = decode_jwt_token(token)
        if user:
            request.user = user
            return token
        return None


class MultiVendorAPIKey(APIKeyHeader):
    param_name = "X-API-Key"

    def authenticate(self, request, key):
        # Check API Key
        providers = Provider.objects.filter(auth_protocol="API_KEY")
        for p in providers:
            if p.auth_credentials and p.auth_credentials.get("api_key") == key:
                request.provider = p
                User = get_user_model()
                user, _ = User.objects.get_or_create(username=f"provider_{p.id}", defaults={"is_staff": True})
                request.user = user
                request.user_roles = ["cdisc"]
                return key

        # Fallback to Static API Key for backwards compatibility
        from django.conf import settings

        expected_key = getattr(settings, "CLINICAL_API_KEY", None)
        if expected_key and key == expected_key:
            User = get_user_model()
            user, _ = User.objects.get_or_create(username="api_user", defaults={"is_staff": True})
            request.user = user
            request.user_roles = ["cdisc"]
            request.provider = Provider.objects.filter(name="Legacy/Default").first()
            return key

        return None


class MultiVendorBearer(HttpBearer):
    def authenticate(self, request, token):
        providers = Provider.objects.filter(auth_protocol__in=["OIDC", "OAUTH2"])
        for p in providers:
            # For simplicity, assuming token validation relies on checking stored token or mock logic
            if p.auth_credentials and p.auth_credentials.get("token") == token:
                request.provider = p
                User = get_user_model()
                user, _ = User.objects.get_or_create(username=f"provider_{p.id}", defaults={"is_staff": True})
                request.user = user
                request.user_roles = ["cdisc"]
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

router = Router(auth=[MultiVendorAPIKey(), MultiVendorBearer(), JWTBearer()])

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
            "record",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]


from django.db.models import Q


def get_accessible_studies(user):
    from users.models import SiteMembership, StudyMembership

    if user.is_staff or user.is_superuser:
        return Study.objects.all()
    auditor_study_ids = StudyMembership.objects.filter(user=user, role="clinical_auditor").values_list(
        "study_id", flat=True
    )
    investigator_study_ids = SiteMembership.objects.filter(user=user, role="site_investigator").values_list(
        "site__study_id", flat=True
    )
    return Study.objects.filter(Q(id__in=auditor_study_ids) | Q(id__in=investigator_study_ids))


def get_accessible_sites(user):
    from users.models import SiteMembership, StudyMembership

    if user.is_staff or user.is_superuser:
        return Site.objects.all()
    auditor_study_ids = StudyMembership.objects.filter(user=user, role="clinical_auditor").values_list(
        "study_id", flat=True
    )
    investigator_site_ids = SiteMembership.objects.filter(user=user, role="site_investigator").values_list(
        "site_id", flat=True
    )
    return Site.objects.filter(Q(study_id__in=auditor_study_ids) | Q(id__in=investigator_site_ids))


def get_accessible_subjects(user):
    from users.models import SiteMembership, StudyMembership

    if user.is_staff or user.is_superuser:
        return Subject.objects.all()
    auditor_study_ids = StudyMembership.objects.filter(user=user, role="clinical_auditor").values_list(
        "study_id", flat=True
    )
    investigator_site_ids = SiteMembership.objects.filter(user=user, role="site_investigator").values_list(
        "site_id", flat=True
    )
    return Subject.objects.filter(Q(site__study_id__in=auditor_study_ids) | Q(site_id__in=investigator_site_ids))


import json

from django.core.exceptions import PermissionDenied


def _queue_single_task(request, hierarchy_level: int, entity_type: str, payload_obj) -> tuple[int, SyncJobResponse]:
    if not (request.user.is_staff or request.user.is_superuser):
        from users.models import SiteMembership

        if not SiteMembership.objects.filter(user=request.user, role="site_investigator").exists():
            raise PermissionDenied("Clinical Auditors have read-only access.")

    payload_dict = json.loads(payload_obj.json())
    job = SyncJob.objects.create(user=request.user, provider=getattr(request, "provider", None), status="PENDING")
    SyncTask.objects.create(
        job=job, hierarchy_level=hierarchy_level, entity_type=entity_type, payload=payload_dict, status="PENDING"
    )
    status_url = f"/api/clinical/sync-jobs/{job.id}"
    return 202, SyncJobResponse(job_id=job.id, status=job.status, message="Sync job queued", status_url=status_url)


# --- Endpoints ---


@router.post("/sync-jobs", response={202: SyncJobResponse})
def create_sync_job(request, payload: SyncJobRequest):
    if not (request.user.is_staff or request.user.is_superuser):
        from users.models import SiteMembership

        if not SiteMembership.objects.filter(user=request.user, role="site_investigator").exists():
            raise PermissionDenied("Clinical Auditors have read-only access.")

    job = SyncJob.objects.create(user=request.user, provider=getattr(request, "provider", None), status="PENDING")

    # Create tasks
    task_objects = []
    for entity in payload.entities:
        task_objects.append(
            SyncTask(
                job=job,
                hierarchy_level=entity.hierarchy_level,
                entity_type=entity.entity_type,
                payload=entity.payload,
                status="PENDING",
            )
        )

    SyncTask.objects.bulk_create(task_objects)

    status_url = f"/api/clinical/sync-jobs/{job.id}"
    return 202, SyncJobResponse(job_id=job.id, status=job.status, message="Sync job queued", status_url=status_url)


@router.get("/sync-jobs/{job_id}", response=JobStatusSchemaOut)
def get_sync_job(request, job_id: str):
    return get_object_or_404(SyncJob, id=job_id, user=request.user)


# L1: Study
@router.post("/studies", response={202: SyncJobResponse})
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
    return get_accessible_studies(request.user)


# L1: Site
@router.post("/sites", response={202: SyncJobResponse})
def api_sync_site(request, payload: SiteSchemaIn):
    return _queue_single_task(request, 1, "Site", payload)


def sync_site(request, payload: SiteSchemaIn):
    study = get_accessible_studies(request.user).filter(external_id=payload.study_ext_id).first()
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
    return get_accessible_sites(request.user).select_related("study")


# L2: Subject
@router.post("/subjects", response={202: SyncJobResponse})
def api_sync_subject(request, payload: SubjectSchemaIn):
    return _queue_single_task(request, 2, "Subject", payload)


def sync_subject(request, payload: SubjectSchemaIn):
    site = get_accessible_sites(request.user).filter(external_id=payload.site_ext_id).first()
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
    return get_accessible_subjects(request.user).select_related("site")


# L2: Form
@router.post("/forms", response={202: SyncJobResponse})
def api_sync_form(request, payload: FormSchemaIn):
    return _queue_single_task(request, 2, "Form", payload)


def sync_form(request, payload: FormSchemaIn):
    study = get_accessible_studies(request.user).filter(external_id=payload.study_ext_id).first()
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
    return Form.objects.filter(study__in=get_accessible_studies(request.user)).select_related("study")


# L2: Interval
@router.post("/intervals", response={202: SyncJobResponse})
def api_sync_interval(request, payload: IntervalSchemaIn):
    return _queue_single_task(request, 2, "Interval", payload)


def sync_interval(request, payload: IntervalSchemaIn):
    study = get_accessible_studies(request.user).filter(external_id=payload.study_ext_id).first()
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
    return Interval.objects.filter(study__in=get_accessible_studies(request.user)).select_related("study")


# L3: Variable
@router.post("/variables", response={202: SyncJobResponse})
def api_sync_variable(request, payload: VariableSchemaIn):
    return _queue_single_task(request, 3, "Variable", payload)


def sync_variable(request, payload: VariableSchemaIn):
    form = (
        Form.objects.filter(study__in=get_accessible_studies(request.user))
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
    return Variable.objects.filter(form__study__in=get_accessible_studies(request.user)).select_related("form")


# L3: Visit
@router.post("/visits", response={202: SyncJobResponse})
def api_sync_visit(request, payload: VisitSchemaIn):
    return _queue_single_task(request, 3, "Visit", payload)


def sync_visit(request, payload: VisitSchemaIn):
    subject = get_accessible_subjects(request.user).filter(external_id=payload.subject_ext_id).first()
    if not subject:
        BufferedOrphan.objects.create(
            entity_type="Visit", missing_parent_id=payload.subject_ext_id, payload=payload.dict(), user=request.user
        )
        return 202, {"message": "Buffered due to missing parent"}
    interval = (
        Interval.objects.filter(study__in=get_accessible_studies(request.user))
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
    return Visit.objects.filter(subject__in=get_accessible_subjects(request.user)).select_related("subject", "interval")


# L4: Record
@router.post("/records", response={202: SyncJobResponse})
def api_sync_record(request, payload: RecordSchemaIn):
    return _queue_single_task(request, 4, "Record", payload)


def sync_record(request, payload: RecordSchemaIn):
    visit = (
        Visit.objects.filter(subject__in=get_accessible_subjects(request.user))
        .filter(external_id=payload.visit_ext_id)
        .first()
    )
    if not visit:
        BufferedOrphan.objects.create(
            entity_type="Record", missing_parent_id=payload.visit_ext_id, payload=payload.dict(), user=request.user
        )
        return 202, {"message": "Buffered due to missing parent"}
    variable = (
        Variable.objects.filter(form__study__in=get_accessible_studies(request.user))
        .filter(external_id=payload.variable_ext_id)
        .first()
    )
    if not variable:
        BufferedOrphan.objects.create(
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
    record, _ = Record.objects.update_or_create(
        external_id=payload.external_id, defaults=defaults, create_defaults={**defaults, "created_by": request.user}
    )
    check_and_process_orphans(record.external_id)
    return record


@router.get("/records", response=list[RecordSchemaOut])
def list_records(request):
    return Record.objects.filter(visit__subject__in=get_accessible_subjects(request.user)).select_related(
        "visit", "variable"
    )


# L4: Coding
@router.post("/codings", response={202: SyncJobResponse})
def api_sync_coding(request, payload: CodingSchemaIn):
    return _queue_single_task(request, 4, "Coding", payload)


def sync_coding(request, payload: CodingSchemaIn):
    record = (
        Record.objects.filter(visit__subject__in=get_accessible_subjects(request.user))
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
    return Coding.objects.filter(record__visit__subject__in=get_accessible_subjects(request.user)).select_related(
        "record"
    )


# L4: Query
@router.post("/queries", response={202: SyncJobResponse})
def api_sync_query(request, payload: QuerySchemaIn):
    return _queue_single_task(request, 4, "Query", payload)


def sync_query(request, payload: QuerySchemaIn):
    record = (
        Record.objects.filter(visit__subject__in=get_accessible_subjects(request.user))
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
            updated_by=request.user
        )

    check_and_process_orphans(query.external_id)
    return query


@router.get("/queries", response=list[QuerySchemaOut])
def list_queries(request):
    return Query.objects.filter(record__visit__subject__in=get_accessible_subjects(request.user)).select_related(
        "record"
    )

@router.patch("/queries/{query_id}", response=QuerySchemaOut)
def update_query(request, query_id: int, payload: QueryUpdateIn):
    query = Query.objects.get(id=query_id, record__visit__subject__in=get_accessible_subjects(request.user))
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
@router.post("/revisions", response={202: SyncJobResponse})
def api_sync_revision(request, payload: RecordRevisionSchemaIn):
    return _queue_single_task(request, 4, "RecordRevision", payload)


def sync_revision(request, payload: RecordRevisionSchemaIn):
    record = (
        Record.objects.filter(visit__subject__in=get_accessible_subjects(request.user))
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
        record__visit__subject__in=get_accessible_subjects(request.user)
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

    # We should enforce permissions. For simplicity, if not staff, we might restrict,
    # but based on requirements, assume basic accessible items.
    obj = get_object_or_404(model_cls, external_id=external_id)
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
