# ruff: noqa: RUF012, ERA001

from django.shortcuts import get_object_or_404
from ninja import ModelSchema, Router

from .export import generate_cdisc_export
from .models import Coding, Form, Interval, Query, Record, RecordRevision, Site, Study, Subject, Variable, Visit

from jobs.models import Job
from jobs.api import JobSchemaOut

router = Router()

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


# L1: Study
@router.post("/studies", response={202: JobSchemaOut})
def sync_study(request, payload: list[StudySchemaIn] | StudySchemaIn):
    payload_data = [item.dict() for item in payload] if isinstance(payload, list) else [payload.dict()]
    job = Job.objects.create(
        job_type="sync_study",
        payload=payload_data
    )
    return 202, job


@router.get("/studies", response=list[StudySchemaOut])
def list_studies(request):
    return Study.objects.all()


# L1: Site
@router.post("/sites", response={202: JobSchemaOut})
def sync_site(request, payload: list[SiteSchemaIn] | SiteSchemaIn):
    payload_data = [item.dict() for item in payload] if isinstance(payload, list) else [payload.dict()]
    job = Job.objects.create(
        job_type="sync_site",
        payload=payload_data
    )
    return 202, job


@router.get("/sites", response=list[SiteSchemaOut])
def list_sites(request):
    return Site.objects.select_related("study").all()


# L2: Subject
@router.post("/subjects", response={202: JobSchemaOut})
def sync_subject(request, payload: list[SubjectSchemaIn] | SubjectSchemaIn):
    payload_data = [item.dict() for item in payload] if isinstance(payload, list) else [payload.dict()]
    job = Job.objects.create(
        job_type="sync_subject",
        payload=payload_data
    )
    return 202, job


@router.get("/subjects", response=list[SubjectSchemaOut])
def list_subjects(request):
    return Subject.objects.select_related("site").all()


# L2: Form
@router.post("/forms", response={202: JobSchemaOut})
def sync_form(request, payload: list[FormSchemaIn] | FormSchemaIn):
    payload_data = [item.dict() for item in payload] if isinstance(payload, list) else [payload.dict()]
    job = Job.objects.create(
        job_type="sync_form",
        payload=payload_data
    )
    return 202, job


@router.get("/forms", response=list[FormSchemaOut])
def list_forms(request):
    return Form.objects.select_related("study").all()


# L2: Interval
@router.post("/intervals", response={202: JobSchemaOut})
def sync_interval(request, payload: list[IntervalSchemaIn] | IntervalSchemaIn):
    payload_data = [item.dict() for item in payload] if isinstance(payload, list) else [payload.dict()]
    job = Job.objects.create(
        job_type="sync_interval",
        payload=payload_data
    )
    return 202, job


@router.get("/intervals", response=list[IntervalSchemaOut])
def list_intervals(request):
    return Interval.objects.select_related("study").all()


# L3: Variable
@router.post("/variables", response={202: JobSchemaOut})
def sync_variable(request, payload: list[VariableSchemaIn] | VariableSchemaIn):
    payload_data = [item.dict() for item in payload] if isinstance(payload, list) else [payload.dict()]
    job = Job.objects.create(
        job_type="sync_variable",
        payload=payload_data
    )
    return 202, job


@router.get("/variables", response=list[VariableSchemaOut])
def list_variables(request):
    return Variable.objects.select_related("form").all()


# L3: Visit
@router.post("/visits", response={202: JobSchemaOut})
def sync_visit(request, payload: list[VisitSchemaIn] | VisitSchemaIn):
    payload_data = [item.dict() for item in payload] if isinstance(payload, list) else [payload.dict()]
    job = Job.objects.create(
        job_type="sync_visit",
        payload=payload_data
    )
    return 202, job


@router.get("/visits", response=list[VisitSchemaOut])
def list_visits(request):
    return Visit.objects.select_related("subject", "interval").all()


# L4: Record
@router.post("/records", response={202: JobSchemaOut})
def sync_record(request, payload: list[RecordSchemaIn] | RecordSchemaIn):
    payload_data = [item.dict() for item in payload] if isinstance(payload, list) else [payload.dict()]
    job = Job.objects.create(
        job_type="sync_record",
        payload=payload_data
    )
    return 202, job


@router.get("/records", response=list[RecordSchemaOut])
def list_records(request):
    return Record.objects.select_related("visit", "variable").all()


# L4: Coding
@router.post("/codings", response={202: JobSchemaOut})
def sync_coding(request, payload: list[CodingSchemaIn] | CodingSchemaIn):
    payload_data = [item.dict() for item in payload] if isinstance(payload, list) else [payload.dict()]
    job = Job.objects.create(
        job_type="sync_coding",
        payload=payload_data
    )
    return 202, job


@router.get("/codings", response=list[CodingSchemaOut])
def list_codings(request):
    return Coding.objects.select_related("record").all()


# L4: Query
@router.post("/queries", response={202: JobSchemaOut})
def sync_query(request, payload: list[QuerySchemaIn] | QuerySchemaIn):
    payload_data = [item.dict() for item in payload] if isinstance(payload, list) else [payload.dict()]
    job = Job.objects.create(
        job_type="sync_query",
        payload=payload_data
    )
    return 202, job


@router.get("/queries", response=list[QuerySchemaOut])
def list_queries(request):
    return Query.objects.select_related("record").all()


# L4: RecordRevision
@router.post("/revisions", response={202: JobSchemaOut})
def sync_revision(request, payload: list[RecordRevisionSchemaIn] | RecordRevisionSchemaIn):
    payload_data = [item.dict() for item in payload] if isinstance(payload, list) else [payload.dict()]
    job = Job.objects.create(
        job_type="sync_revision",
        payload=payload_data
    )
    return 202, job


@router.get("/revisions", response=list[RecordRevisionSchemaOut])
def list_revisions(request):
    return RecordRevision.objects.select_related("record").all()




@router.get("/export/cdisc")
def export_cdisc_package(request):
    return generate_cdisc_export(request)
