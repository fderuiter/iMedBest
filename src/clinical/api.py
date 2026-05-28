# ruff: noqa: RUF012, ERA001

from django.conf import settings
from django.shortcuts import get_object_or_404
from ninja import ModelSchema, Router
from ninja.security import APIKeyHeader


class StaticAPIKey(APIKeyHeader):
    param_name = "X-API-Key"

    def authenticate(self, request, key):
        expected_key = getattr(settings, "CLINICAL_API_KEY", None)
        if expected_key and key == expected_key:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user, _ = User.objects.get_or_create(username="api_user", defaults={"is_staff": True})
            request.user = user
            request.user_roles = ['cdisc']
            return key
        return None

from .models import (
    Coding,
    ExportJob,
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
from .schemas import ExportJobResponse, SyncJobRequest, SyncJobResponse
from .tasks import orchestrate_sync_job, process_export_job

router = Router(auth=StaticAPIKey())

# --- Schemas ---

class ExportJobSchemaOut(ModelSchema):
    class Meta:
        model = ExportJob
        fields = ["id", "status", "error_message", "created_at", "updated_at"]

class JobStatusSchemaOut(ModelSchema):
    class Meta:
        model = SyncJob
        fields = ["id", "status", "error_message", "created_at", "updated_at"]



class StudySchemaIn(ModelSchema):
    class Meta:
        model = Study
        fields = ["clinical_timestamp", "source_sequence", "external_id", "name"]


class StudySchemaOut(ModelSchema):
    class Meta:
        model = Study
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "name", "created_at", "updated_at", "created_by", "updated_by"]


class SiteSchemaIn(ModelSchema):
    study_ext_id: str

    class Meta:
        model = Site
        fields = ["clinical_timestamp", "source_sequence", "external_id", "name"]


class SiteSchemaOut(ModelSchema):
    class Meta:
        model = Site
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "name", "study", "created_at", "updated_at", "created_by", "updated_by"]


class SubjectSchemaIn(ModelSchema):
    site_ext_id: str

    class Meta:
        model = Subject
        fields = ["clinical_timestamp", "source_sequence", "external_id", "name"]


class SubjectSchemaOut(ModelSchema):
    class Meta:
        model = Subject
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "name", "site", "created_at", "updated_at", "created_by", "updated_by"]


class FormSchemaIn(ModelSchema):
    study_ext_id: str

    class Meta:
        model = Form
        fields = ["clinical_timestamp", "source_sequence", "external_id", "name"]


class FormSchemaOut(ModelSchema):
    class Meta:
        model = Form
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "name", "study", "created_at", "updated_at", "created_by", "updated_by"]


class IntervalSchemaIn(ModelSchema):
    study_ext_id: str

    class Meta:
        model = Interval
        fields = ["clinical_timestamp", "source_sequence", "external_id", "name"]


class IntervalSchemaOut(ModelSchema):
    class Meta:
        model = Interval
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "name", "study", "created_at", "updated_at", "created_by", "updated_by"]


class VariableSchemaIn(ModelSchema):
    form_ext_id: str

    class Meta:
        model = Variable
        fields = ["clinical_timestamp", "source_sequence", "external_id", "name"]


class VariableSchemaOut(ModelSchema):
    class Meta:
        model = Variable
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "name", "form", "created_at", "updated_at", "created_by", "updated_by"]


class VisitSchemaIn(ModelSchema):
    subject_ext_id: str
    interval_ext_id: str

    class Meta:
        model = Visit
        fields = ["clinical_timestamp", "source_sequence", "external_id"]


class VisitSchemaOut(ModelSchema):
    class Meta:
        model = Visit
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "subject", "interval", "created_at", "updated_at", "created_by", "updated_by"]


class RecordSchemaIn(ModelSchema):
    visit_ext_id: str
    variable_ext_id: str

    class Meta:
        model = Record
        fields = ["clinical_timestamp", "source_sequence", "external_id", "value"]


class RecordSchemaOut(ModelSchema):
    class Meta:
        model = Record
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "value", "visit", "variable", "created_at", "updated_at", "created_by", "updated_by"]


class CodingSchemaIn(ModelSchema):
    record_ext_id: str

    class Meta:
        model = Coding
        fields = ["clinical_timestamp", "source_sequence", "external_id", "code"]


class CodingSchemaOut(ModelSchema):
    class Meta:
        model = Coding
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "code", "record", "created_at", "updated_at", "created_by", "updated_by"]


class QuerySchemaIn(ModelSchema):
    record_ext_id: str

    class Meta:
        model = Query
        fields = ["clinical_timestamp", "source_sequence", "external_id", "text"]


class QuerySchemaOut(ModelSchema):
    class Meta:
        model = Query
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "text", "record", "created_at", "updated_at", "created_by", "updated_by"]


class RecordRevisionSchemaIn(ModelSchema):
    record_ext_id: str

    class Meta:
        model = RecordRevision
        fields = ["clinical_timestamp", "source_sequence", "external_id", "value"]


class RecordRevisionSchemaOut(ModelSchema):
    class Meta:
        model = RecordRevision
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "value", "record", "created_at", "updated_at", "created_by", "updated_by"]


from django.db.models import Q


def get_accessible_studies(user):
    from users.models import SiteMembership, StudyMembership
    if user.is_staff or user.is_superuser:
        return Study.objects.all()
    auditor_study_ids = StudyMembership.objects.filter(user=user, role='clinical_auditor').values_list('study_id', flat=True)
    investigator_study_ids = SiteMembership.objects.filter(user=user, role='site_investigator').values_list('site__study_id', flat=True)
    return Study.objects.filter(Q(id__in=auditor_study_ids) | Q(id__in=investigator_study_ids))

def get_accessible_sites(user):
    from users.models import SiteMembership, StudyMembership
    if user.is_staff or user.is_superuser:
        return Site.objects.all()
    auditor_study_ids = StudyMembership.objects.filter(user=user, role='clinical_auditor').values_list('study_id', flat=True)
    investigator_site_ids = SiteMembership.objects.filter(user=user, role='site_investigator').values_list('site_id', flat=True)
    return Site.objects.filter(Q(study_id__in=auditor_study_ids) | Q(id__in=investigator_site_ids))

def get_accessible_subjects(user):
    from users.models import SiteMembership, StudyMembership
    if user.is_staff or user.is_superuser:
        return Subject.objects.all()
    auditor_study_ids = StudyMembership.objects.filter(user=user, role='clinical_auditor').values_list('study_id', flat=True)
    investigator_site_ids = SiteMembership.objects.filter(user=user, role='site_investigator').values_list('site_id', flat=True)
    return Subject.objects.filter(Q(site__study_id__in=auditor_study_ids) | Q(site_id__in=investigator_site_ids))

# --- Endpoints ---

@router.post("/sync-jobs", response={202: SyncJobResponse})
def create_sync_job(request, payload: SyncJobRequest):
    job = SyncJob.objects.create(
        user=request.user,
        status='PENDING'
    )

    # Create tasks
    task_objects = []
    for entity in payload.entities:
        task_objects.append(SyncTask(
            job=job,
            hierarchy_level=entity.hierarchy_level,
            entity_type=entity.entity_type,
            payload=entity.payload,
            status='PENDING'
        ))

    SyncTask.objects.bulk_create(task_objects)

    # Start orchestration
    orchestrate_sync_job.delay(job.id, request.user.id)

    return 202, SyncJobResponse(job_id=job.id, status=job.status, message="Sync job queued")

@router.get("/sync-jobs/{job_id}", response=JobStatusSchemaOut)
def get_sync_job(request, job_id: str):
    return get_object_or_404(SyncJob, id=job_id, user=request.user)

# L1: Study
@router.post("/studies", response=StudySchemaOut)
def sync_study(request, payload: StudySchemaIn):
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "name": payload.name,
        "updated_by": request.user
    }
    study, _ = Study.objects.update_or_create(
        external_id=payload.external_id,
        defaults=defaults,
        create_defaults={**defaults, "created_by": request.user}
    )
    return study


@router.get("/studies", response=list[StudySchemaOut])
def list_studies(request):
    return get_accessible_studies(request.user)


# L1: Site
@router.post("/sites", response=SiteSchemaOut)
def sync_site(request, payload: SiteSchemaIn):
    study = get_object_or_404(get_accessible_studies(request.user), external_id=payload.study_ext_id)
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "study": study,
        "name": payload.name,
        "updated_by": request.user
    }
    site, _ = Site.objects.update_or_create(
        external_id=payload.external_id,
        defaults=defaults,
        create_defaults={**defaults, "created_by": request.user}
    )
    return site


@router.get("/sites", response=list[SiteSchemaOut])
def list_sites(request):
    return get_accessible_sites(request.user).select_related("study")


# L2: Subject
@router.post("/subjects", response=SubjectSchemaOut)
def sync_subject(request, payload: SubjectSchemaIn):
    site = get_object_or_404(get_accessible_sites(request.user), external_id=payload.site_ext_id)
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "site": site,
        "name": payload.name,
        "updated_by": request.user
    }
    subject, _ = Subject.objects.update_or_create(
        external_id=payload.external_id,
        defaults=defaults,
        create_defaults={**defaults, "created_by": request.user}
    )
    return subject


@router.get("/subjects", response=list[SubjectSchemaOut])
def list_subjects(request):
    return get_accessible_subjects(request.user).select_related("site")


# L2: Form
@router.post("/forms", response=FormSchemaOut)
def sync_form(request, payload: FormSchemaIn):
    study = get_object_or_404(get_accessible_studies(request.user), external_id=payload.study_ext_id)
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "study": study,
        "name": payload.name,
        "updated_by": request.user
    }
    form, _ = Form.objects.update_or_create(
        external_id=payload.external_id,
        defaults=defaults,
        create_defaults={**defaults, "created_by": request.user}
    )
    return form


@router.get("/forms", response=list[FormSchemaOut])
def list_forms(request):
    return Form.objects.filter(study__in=get_accessible_studies(request.user)).select_related("study")


# L2: Interval
@router.post("/intervals", response=IntervalSchemaOut)
def sync_interval(request, payload: IntervalSchemaIn):
    study = get_object_or_404(get_accessible_studies(request.user), external_id=payload.study_ext_id)
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "study": study,
        "name": payload.name,
        "updated_by": request.user
    }
    interval, _ = Interval.objects.update_or_create(
        external_id=payload.external_id,
        defaults=defaults,
        create_defaults={**defaults, "created_by": request.user}
    )
    return interval


@router.get("/intervals", response=list[IntervalSchemaOut])
def list_intervals(request):
    return Interval.objects.filter(study__in=get_accessible_studies(request.user)).select_related("study")


# L3: Variable
@router.post("/variables", response=VariableSchemaOut)
def sync_variable(request, payload: VariableSchemaIn):
    form = get_object_or_404(Form.objects.filter(study__in=get_accessible_studies(request.user)), external_id=payload.form_ext_id)
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "form": form,
        "name": payload.name,
        "updated_by": request.user
    }
    variable, _ = Variable.objects.update_or_create(
        external_id=payload.external_id,
        defaults=defaults,
        create_defaults={**defaults, "created_by": request.user}
    )
    return variable


@router.get("/variables", response=list[VariableSchemaOut])
def list_variables(request):
    return Variable.objects.filter(form__study__in=get_accessible_studies(request.user)).select_related("form")


# L3: Visit
@router.post("/visits", response=VisitSchemaOut)
def sync_visit(request, payload: VisitSchemaIn):
    subject = get_object_or_404(get_accessible_subjects(request.user), external_id=payload.subject_ext_id)
    interval = get_object_or_404(Interval.objects.filter(study__in=get_accessible_studies(request.user)), external_id=payload.interval_ext_id)
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "subject": subject,
        "interval": interval,
        "updated_by": request.user
    }
    visit, _ = Visit.objects.update_or_create(
        external_id=payload.external_id,
        defaults=defaults,
        create_defaults={**defaults, "created_by": request.user}
    )
    return visit


@router.get("/visits", response=list[VisitSchemaOut])
def list_visits(request):
    return Visit.objects.filter(subject__in=get_accessible_subjects(request.user)).select_related("subject", "interval")


# L4: Record
@router.post("/records", response=RecordSchemaOut)
def sync_record(request, payload: RecordSchemaIn):
    visit = get_object_or_404(Visit.objects.filter(subject__in=get_accessible_subjects(request.user)), external_id=payload.visit_ext_id)
    variable = get_object_or_404(Variable.objects.filter(form__study__in=get_accessible_studies(request.user)), external_id=payload.variable_ext_id)
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "visit": visit,
        "variable": variable,
        "value": payload.value,
        "updated_by": request.user
    }
    record, _ = Record.objects.update_or_create(
        external_id=payload.external_id,
        defaults=defaults,
        create_defaults={**defaults, "created_by": request.user}
    )
    return record


@router.get("/records", response=list[RecordSchemaOut])
def list_records(request):
    return Record.objects.filter(visit__subject__in=get_accessible_subjects(request.user)).select_related("visit", "variable")


# L4: Coding
@router.post("/codings", response=CodingSchemaOut)
def sync_coding(request, payload: CodingSchemaIn):
    record = get_object_or_404(Record.objects.filter(visit__subject__in=get_accessible_subjects(request.user)), external_id=payload.record_ext_id)
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "record": record,
        "code": payload.code,
        "updated_by": request.user
    }
    coding, _ = Coding.objects.update_or_create(
        external_id=payload.external_id,
        defaults=defaults,
        create_defaults={**defaults, "created_by": request.user}
    )
    return coding


@router.get("/codings", response=list[CodingSchemaOut])
def list_codings(request):
    return Coding.objects.filter(record__visit__subject__in=get_accessible_subjects(request.user)).select_related("record")


# L4: Query
@router.post("/queries", response=QuerySchemaOut)
def sync_query(request, payload: QuerySchemaIn):
    record = get_object_or_404(Record.objects.filter(visit__subject__in=get_accessible_subjects(request.user)), external_id=payload.record_ext_id)
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "record": record,
        "text": payload.text,
        "updated_by": request.user
    }
    query, _ = Query.objects.update_or_create(
        external_id=payload.external_id,
        defaults=defaults,
        create_defaults={**defaults, "created_by": request.user}
    )
    return query


@router.get("/queries", response=list[QuerySchemaOut])
def list_queries(request):
    return Query.objects.filter(record__visit__subject__in=get_accessible_subjects(request.user)).select_related("record")


# L4: RecordRevision
@router.post("/revisions", response=RecordRevisionSchemaOut)
def sync_revision(request, payload: RecordRevisionSchemaIn):
    record = get_object_or_404(Record.objects.filter(visit__subject__in=get_accessible_subjects(request.user)), external_id=payload.record_ext_id)
    defaults = {
        "clinical_timestamp": payload.clinical_timestamp,
        "source_sequence": payload.source_sequence,
        "record": record,
        "value": payload.value,
        "updated_by": request.user
    }
    revision, _ = RecordRevision.objects.update_or_create(
        external_id=payload.external_id,
        defaults=defaults,
        create_defaults={**defaults, "created_by": request.user}
    )
    return revision


@router.get("/revisions", response=list[RecordRevisionSchemaOut])
def list_revisions(request):
    return RecordRevision.objects.filter(record__visit__subject__in=get_accessible_subjects(request.user)).select_related("record")




@router.post("/export/cdisc", response={202: ExportJobResponse})
def export_cdisc_package(request):
    # Check data-extraction privileges
    roles = getattr(request, 'user_roles', [])
    has_privilege = any(r in str(roles).lower() for r in ['export', 'extractor', 'cdisc'])
    if not (has_privilege or request.user.is_staff or request.user.is_superuser):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Missing data-extraction privileges")

    job = ExportJob.objects.create(
        user=request.user,
        status='PENDING'
    )

    process_export_job.delay(job.id)

    return 202, ExportJobResponse(job_id=job.id, status=job.status, message="Export job queued")

@router.get("/export/jobs", response=list[ExportJobSchemaOut])
def list_export_jobs(request):
    return ExportJob.objects.filter(user=request.user).order_by('-created_at')

@router.get("/export/jobs/{job_id}", response=ExportJobSchemaOut)
def get_export_job(request, job_id: str):
    return get_object_or_404(ExportJob, id=job_id, user=request.user)

@router.post("/export/jobs/{job_id}/retry", response={202: ExportJobResponse})
def retry_export_job(request, job_id: str):
    job = get_object_or_404(ExportJob, id=job_id, user=request.user)
    if job.status == 'COMPLETED':
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest("Job already completed")

    job.status = 'PENDING'
    job.error_message = None
    job.save(update_fields=['status', 'error_message'])

    process_export_job.delay(job.id)

    return 202, ExportJobResponse(job_id=job.id, status=job.status, message="Export job re-queued")

@router.get("/export/jobs/{job_id}/download")
def download_export_job(request, job_id: str):
    job = get_object_or_404(ExportJob, id=job_id, user=request.user)
    if job.status != 'COMPLETED' or not job.file:
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest("File not ready")

    from django.http import FileResponse
    response = FileResponse(job.file.open('rb'), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="cdisc_export_{job.id}.zip"'
    return response
