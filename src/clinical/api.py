import uuid

from django.shortcuts import get_object_or_404
from ninja import ModelSchema, Router
from pydantic import BaseModel

from async_jobs.models import Job

from .export import generate_cdisc_export
from .models import Coding, Form, Interval, Query, Record, RecordRevision, Site, Study, Subject, Variable, Visit

router = Router()

class JobResponseSchema(BaseModel):
    job_token: uuid.UUID
    status: str

class JobStatusSchema(BaseModel):
    job_token: uuid.UUID
    status: str
    result: dict | None = None
    error: str | None = None

# --- Schemas ---

class StudySchemaIn(ModelSchema):
    class Meta:
        model = Study
        fields = ["external_id", "name"]

class StudySchemaOut(ModelSchema):
    class Meta:
        model = Study
        fields = ["id", "external_id", "name", "created_at", "updated_at"]

class SiteSchemaIn(ModelSchema):
    study_ext_id: str
    class Meta:
        model = Site
        fields = ["external_id", "name"]

class SiteSchemaOut(ModelSchema):
    class Meta:
        model = Site
        fields = ["id", "external_id", "name", "study", "created_at", "updated_at"]

class SubjectSchemaIn(ModelSchema):
    site_ext_id: str
    class Meta:
        model = Subject
        fields = ["external_id", "name"]

class SubjectSchemaOut(ModelSchema):
    class Meta:
        model = Subject
        fields = ["id", "external_id", "name", "site", "created_at", "updated_at"]

class FormSchemaIn(ModelSchema):
    study_ext_id: str
    class Meta:
        model = Form
        fields = ["external_id", "name"]

class FormSchemaOut(ModelSchema):
    class Meta:
        model = Form
        fields = ["id", "external_id", "name", "study", "created_at", "updated_at"]

class IntervalSchemaIn(ModelSchema):
    study_ext_id: str
    class Meta:
        model = Interval
        fields = ["external_id", "name"]

class IntervalSchemaOut(ModelSchema):
    class Meta:
        model = Interval
        fields = ["id", "external_id", "name", "study", "created_at", "updated_at"]

class VariableSchemaIn(ModelSchema):
    form_ext_id: str
    class Meta:
        model = Variable
        fields = ["external_id", "name"]

class VariableSchemaOut(ModelSchema):
    class Meta:
        model = Variable
        fields = ["id", "external_id", "name", "form", "created_at", "updated_at"]

class VisitSchemaIn(ModelSchema):
    subject_ext_id: str
    interval_ext_id: str
    class Meta:
        model = Visit
        fields = ["external_id"]

class VisitSchemaOut(ModelSchema):
    class Meta:
        model = Visit
        fields = ["id", "external_id", "subject", "interval", "created_at", "updated_at"]

class RecordSchemaIn(ModelSchema):
    visit_ext_id: str
    variable_ext_id: str
    class Meta:
        model = Record
        fields = ["external_id", "value"]

class RecordSchemaOut(ModelSchema):
    class Meta:
        model = Record
        fields = ["id", "external_id", "value", "visit", "variable", "created_at", "updated_at"]

class CodingSchemaIn(ModelSchema):
    record_ext_id: str
    class Meta:
        model = Coding
        fields = ["external_id", "code"]

class CodingSchemaOut(ModelSchema):
    class Meta:
        model = Coding
        fields = ["id", "external_id", "code", "record", "created_at", "updated_at"]

class QuerySchemaIn(ModelSchema):
    record_ext_id: str
    class Meta:
        model = Query
        fields = ["external_id", "text"]

class QuerySchemaOut(ModelSchema):
    class Meta:
        model = Query
        fields = ["id", "external_id", "text", "record", "created_at", "updated_at"]

class RecordRevisionSchemaIn(ModelSchema):
    record_ext_id: str
    class Meta:
        model = RecordRevision
        fields = ["external_id", "value"]

class RecordRevisionSchemaOut(ModelSchema):
    class Meta:
        model = RecordRevision
        fields = ["id", "external_id", "value", "record", "created_at", "updated_at"]


# --- Endpoints ---

def create_job(endpoint_name: str, payload: BaseModel) -> JobResponseSchema:
    job = Job.objects.create(
        endpoint=endpoint_name,
        payload=payload.dict()
    )
    return JobResponseSchema(job_token=job.id, status=job.status)

@router.get("/jobs/{job_token}", response=JobStatusSchema)
def get_job_status(request, job_token: uuid.UUID):
    job = get_object_or_404(Job, id=job_token)
    return JobStatusSchema(
        job_token=job.id,
        status=job.status,
        result=job.result,
        error=job.error
    )

# L1: Study
@router.post("/studies", response=JobResponseSchema)
def sync_study_api(request, payload: StudySchemaIn):
    return create_job("sync_study", payload)

@router.get("/studies", response=list[StudySchemaOut])
def list_studies(request):
    return Study.objects.all()

# L1: Site
@router.post("/sites", response=JobResponseSchema)
def sync_site_api(request, payload: SiteSchemaIn):
    return create_job("sync_site", payload)

@router.get("/sites", response=list[SiteSchemaOut])
def list_sites(request):
    return Site.objects.select_related("study").all()

# L2: Subject
@router.post("/subjects", response=JobResponseSchema)
def sync_subject_api(request, payload: SubjectSchemaIn):
    return create_job("sync_subject", payload)

@router.get("/subjects", response=list[SubjectSchemaOut])
def list_subjects(request):
    return Subject.objects.select_related("site").all()

# L2: Form
@router.post("/forms", response=JobResponseSchema)
def sync_form_api(request, payload: FormSchemaIn):
    return create_job("sync_form", payload)

@router.get("/forms", response=list[FormSchemaOut])
def list_forms(request):
    return Form.objects.select_related("study").all()

# L2: Interval
@router.post("/intervals", response=JobResponseSchema)
def sync_interval_api(request, payload: IntervalSchemaIn):
    return create_job("sync_interval", payload)

@router.get("/intervals", response=list[IntervalSchemaOut])
def list_intervals(request):
    return Interval.objects.select_related("study").all()

# L3: Variable
@router.post("/variables", response=JobResponseSchema)
def sync_variable_api(request, payload: VariableSchemaIn):
    return create_job("sync_variable", payload)

@router.get("/variables", response=list[VariableSchemaOut])
def list_variables(request):
    return Variable.objects.select_related("form").all()

# L3: Visit
@router.post("/visits", response=JobResponseSchema)
def sync_visit_api(request, payload: VisitSchemaIn):
    return create_job("sync_visit", payload)

@router.get("/visits", response=list[VisitSchemaOut])
def list_visits(request):
    return Visit.objects.select_related("subject", "interval").all()

# L4: Record
@router.post("/records", response=JobResponseSchema)
def sync_record_api(request, payload: RecordSchemaIn):
    return create_job("sync_record", payload)

@router.get("/records", response=list[RecordSchemaOut])
def list_records(request):
    return Record.objects.select_related("visit", "variable").all()

# L4: Coding
@router.post("/codings", response=JobResponseSchema)
def sync_coding_api(request, payload: CodingSchemaIn):
    return create_job("sync_coding", payload)

@router.get("/codings", response=list[CodingSchemaOut])
def list_codings(request):
    return Coding.objects.select_related("record").all()

# L4: Query
@router.post("/queries", response=JobResponseSchema)
def sync_query_api(request, payload: QuerySchemaIn):
    return create_job("sync_query", payload)

@router.get("/queries", response=list[QuerySchemaOut])
def list_queries(request):
    return Query.objects.select_related("record").all()

# L4: RecordRevision
@router.post("/revisions", response=JobResponseSchema)
def sync_revision_api(request, payload: RecordRevisionSchemaIn):
    return create_job("sync_revision", payload)

@router.get("/revisions", response=list[RecordRevisionSchemaOut])
def list_revisions(request):
    return RecordRevision.objects.select_related("record").all()

@router.get("/export/cdisc")
def export_cdisc_package(request):
    return generate_cdisc_export(request)
