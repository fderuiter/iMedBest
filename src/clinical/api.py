# ruff: noqa: RUF012, ERA001

from django.shortcuts import get_object_or_404
from ninja import ModelSchema, Router

from users.auth import OIDCBearer

from .export import generate_cdisc_export
from .models import (
    Coding,
    Form,
    Interval,
    Query,
    Record,
    RecordRevision,
    Site,
    Study,
    Subject,
    Variable,
    Visit,
    SyncStatus,
)

router = Router(auth=OIDCBearer())

# --- Schemas ---


class SyncStatusSchemaOut(ModelSchema):
    class Meta:
        model = SyncStatus
        fields = ["last_successful_pull", "status", "error_message", "updated_at"]


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
        ]


class QuerySchemaIn(ModelSchema):
    record_ext_id: str

    class Meta:
        model = Query
        fields = ["clinical_timestamp", "source_sequence", "external_id", "text"]


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
            "record",
            "created_at",
            "updated_at",
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
        ]


# --- Endpoints ---


# L1: Study
@router.post("/studies", response=StudySchemaOut)
def sync_study(request, payload: StudySchemaIn):
    study, _ = Study.objects.update_or_create(
        external_id=payload.external_id,
        defaults={
            "clinical_timestamp": payload.clinical_timestamp,
            "source_sequence": payload.source_sequence,
            "name": payload.name,
        },
    )
    return study


@router.get("/studies", response=list[StudySchemaOut])
def list_studies(request):
    return Study.objects.all()


# L1: Site
@router.post("/sites", response=SiteSchemaOut)
def sync_site(request, payload: SiteSchemaIn):
    study = get_object_or_404(Study, external_id=payload.study_ext_id)
    site, _ = Site.objects.update_or_create(
        external_id=payload.external_id,
        defaults={
            "clinical_timestamp": payload.clinical_timestamp,
            "source_sequence": payload.source_sequence,
            "study": study,
            "name": payload.name,
        },
    )
    return site


@router.get("/sites", response=list[SiteSchemaOut])
def list_sites(request):
    return Site.objects.select_related("study").all()


# L2: Subject
@router.post("/subjects", response=SubjectSchemaOut)
def sync_subject(request, payload: SubjectSchemaIn):
    site = get_object_or_404(Site, external_id=payload.site_ext_id)
    subject, _ = Subject.objects.update_or_create(
        external_id=payload.external_id,
        defaults={
            "clinical_timestamp": payload.clinical_timestamp,
            "source_sequence": payload.source_sequence,
            "site": site,
            "name": payload.name,
        },
    )
    return subject


@router.get("/subjects", response=list[SubjectSchemaOut])
def list_subjects(request):
    return Subject.objects.select_related("site").all()


# L2: Form
@router.post("/forms", response=FormSchemaOut)
def sync_form(request, payload: FormSchemaIn):
    study = get_object_or_404(Study, external_id=payload.study_ext_id)
    form, _ = Form.objects.update_or_create(
        external_id=payload.external_id,
        defaults={
            "clinical_timestamp": payload.clinical_timestamp,
            "source_sequence": payload.source_sequence,
            "study": study,
            "name": payload.name,
        },
    )
    return form


@router.get("/forms", response=list[FormSchemaOut])
def list_forms(request):
    return Form.objects.select_related("study").all()


# L2: Interval
@router.post("/intervals", response=IntervalSchemaOut)
def sync_interval(request, payload: IntervalSchemaIn):
    study = get_object_or_404(Study, external_id=payload.study_ext_id)
    interval, _ = Interval.objects.update_or_create(
        external_id=payload.external_id,
        defaults={
            "clinical_timestamp": payload.clinical_timestamp,
            "source_sequence": payload.source_sequence,
            "study": study,
            "name": payload.name,
        },
    )
    return interval


@router.get("/intervals", response=list[IntervalSchemaOut])
def list_intervals(request):
    return Interval.objects.select_related("study").all()


# L3: Variable
@router.post("/variables", response=VariableSchemaOut)
def sync_variable(request, payload: VariableSchemaIn):
    form = get_object_or_404(Form, external_id=payload.form_ext_id)
    variable, _ = Variable.objects.update_or_create(
        external_id=payload.external_id,
        defaults={
            "clinical_timestamp": payload.clinical_timestamp,
            "source_sequence": payload.source_sequence,
            "form": form,
            "name": payload.name,
        },
    )
    return variable


@router.get("/variables", response=list[VariableSchemaOut])
def list_variables(request):
    return Variable.objects.select_related("form").all()


# L3: Visit
@router.post("/visits", response=VisitSchemaOut)
def sync_visit(request, payload: VisitSchemaIn):
    subject = get_object_or_404(Subject, external_id=payload.subject_ext_id)
    interval = get_object_or_404(Interval, external_id=payload.interval_ext_id)
    visit, _ = Visit.objects.update_or_create(
        external_id=payload.external_id,
        defaults={
            "clinical_timestamp": payload.clinical_timestamp,
            "source_sequence": payload.source_sequence,
            "subject": subject,
            "interval": interval,
        },
    )
    return visit


@router.get("/visits", response=list[VisitSchemaOut])
def list_visits(request):
    return Visit.objects.select_related("subject", "interval").all()


# L4: Record
@router.post("/records", response=RecordSchemaOut)
def sync_record(request, payload: RecordSchemaIn):
    visit = get_object_or_404(Visit, external_id=payload.visit_ext_id)
    variable = get_object_or_404(Variable, external_id=payload.variable_ext_id)
    record, _ = Record.objects.update_or_create(
        external_id=payload.external_id,
        defaults={
            "clinical_timestamp": payload.clinical_timestamp,
            "source_sequence": payload.source_sequence,
            "visit": visit,
            "variable": variable,
            "value": payload.value,
        },
    )
    return record


@router.get("/records", response=list[RecordSchemaOut])
def list_records(request):
    return Record.objects.select_related("visit", "variable").all()


# L4: Coding
@router.post("/codings", response=CodingSchemaOut)
def sync_coding(request, payload: CodingSchemaIn):
    record = get_object_or_404(Record, external_id=payload.record_ext_id)
    coding, _ = Coding.objects.update_or_create(
        external_id=payload.external_id,
        defaults={
            "clinical_timestamp": payload.clinical_timestamp,
            "source_sequence": payload.source_sequence,
            "record": record,
            "code": payload.code,
        },
    )
    return coding


@router.get("/codings", response=list[CodingSchemaOut])
def list_codings(request):
    return Coding.objects.select_related("record").all()


# L4: Query
@router.post("/queries", response=QuerySchemaOut)
def sync_query(request, payload: QuerySchemaIn):
    record = get_object_or_404(Record, external_id=payload.record_ext_id)
    query, _ = Query.objects.update_or_create(
        external_id=payload.external_id,
        defaults={
            "clinical_timestamp": payload.clinical_timestamp,
            "source_sequence": payload.source_sequence,
            "record": record,
            "text": payload.text,
        },
    )
    return query


@router.get("/queries", response=list[QuerySchemaOut])
def list_queries(request):
    return Query.objects.select_related("record").all()


# L4: RecordRevision
@router.post("/revisions", response=RecordRevisionSchemaOut)
def sync_revision(request, payload: RecordRevisionSchemaIn):
    record = get_object_or_404(Record, external_id=payload.record_ext_id)
    revision, _ = RecordRevision.objects.update_or_create(
        external_id=payload.external_id,
        defaults={
            "clinical_timestamp": payload.clinical_timestamp,
            "source_sequence": payload.source_sequence,
            "record": record,
            "value": payload.value,
        },
    )
    return revision


@router.get("/revisions", response=list[RecordRevisionSchemaOut])
def list_revisions(request):
    return RecordRevision.objects.select_related("record").all()


@router.get("/export/cdisc")
def export_cdisc_package(request):
    # Check data-extraction privileges
    roles = getattr(request, "user_roles", [])
    has_privilege = any(r in str(roles).lower() for r in ["export", "extractor", "cdisc"])
    if not (has_privilege or request.user.is_staff or request.user.is_superuser):
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Missing data-extraction privileges")
    return generate_cdisc_export(request)


@router.get("/sync-status", response=SyncStatusSchemaOut)
def get_sync_status(request):
    status_obj, _ = SyncStatus.objects.get_or_create(id=1)
    return status_obj
