# ruff: noqa: RUF012, ERA001

from django.shortcuts import get_object_or_404
from ninja import ModelSchema, Router

from .auth import MultiAuth
from .adapter import HierarchyAdapter
from .export import generate_cdisc_export
from .models import Coding, Form, Interval, Query, Record, RecordRevision, Site, Study, Subject, Variable, Visit

router = Router(auth=MultiAuth())

# --- Schemas ---

class StudySchemaIn(ModelSchema):
    model_config = {"extra": "allow"}
    class Meta:
        model = Study
        fields = ["clinical_timestamp", "source_sequence", "external_id", "name"]

class StudySchemaOut(ModelSchema):
    class Meta:
        model = Study
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "name", "created_at", "updated_at"]

class SiteSchemaIn(ModelSchema):
    model_config = {"extra": "allow"}
    study_ext_id: str | None = None

    class Meta:
        model = Site
        fields = ["clinical_timestamp", "source_sequence", "external_id", "name"]

class SiteSchemaOut(ModelSchema):
    class Meta:
        model = Site
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "name", "study", "created_at", "updated_at"]

class SubjectSchemaIn(ModelSchema):
    model_config = {"extra": "allow"}
    site_ext_id: str | None = None

    class Meta:
        model = Subject
        fields = ["clinical_timestamp", "source_sequence", "external_id", "name"]

class SubjectSchemaOut(ModelSchema):
    class Meta:
        model = Subject
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "name", "site", "created_at", "updated_at"]

class FormSchemaIn(ModelSchema):
    model_config = {"extra": "allow"}
    study_ext_id: str | None = None

    class Meta:
        model = Form
        fields = ["clinical_timestamp", "source_sequence", "external_id", "name"]

class FormSchemaOut(ModelSchema):
    class Meta:
        model = Form
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "name", "study", "created_at", "updated_at"]

class IntervalSchemaIn(ModelSchema):
    model_config = {"extra": "allow"}
    study_ext_id: str | None = None

    class Meta:
        model = Interval
        fields = ["clinical_timestamp", "source_sequence", "external_id", "name"]

class IntervalSchemaOut(ModelSchema):
    class Meta:
        model = Interval
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "name", "study", "created_at", "updated_at"]

class VariableSchemaIn(ModelSchema):
    model_config = {"extra": "allow"}
    form_ext_id: str | None = None

    class Meta:
        model = Variable
        fields = ["clinical_timestamp", "source_sequence", "external_id", "name"]

class VariableSchemaOut(ModelSchema):
    class Meta:
        model = Variable
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "name", "form", "created_at", "updated_at"]

class VisitSchemaIn(ModelSchema):
    model_config = {"extra": "allow"}
    subject_ext_id: str | None = None
    interval_ext_id: str | None = None

    class Meta:
        model = Visit
        fields = ["clinical_timestamp", "source_sequence", "external_id"]

class VisitSchemaOut(ModelSchema):
    class Meta:
        model = Visit
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "subject", "interval", "created_at", "updated_at"]

class RecordSchemaIn(ModelSchema):
    model_config = {"extra": "allow"}
    visit_ext_id: str | None = None
    variable_ext_id: str | None = None

    class Meta:
        model = Record
        fields = ["clinical_timestamp", "source_sequence", "external_id", "value"]

class RecordSchemaOut(ModelSchema):
    class Meta:
        model = Record
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "value", "visit", "variable", "created_at", "updated_at"]

class CodingSchemaIn(ModelSchema):
    model_config = {"extra": "allow"}
    record_ext_id: str | None = None

    class Meta:
        model = Coding
        fields = ["clinical_timestamp", "source_sequence", "external_id", "code"]

class CodingSchemaOut(ModelSchema):
    class Meta:
        model = Coding
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "code", "record", "created_at", "updated_at"]

class QuerySchemaIn(ModelSchema):
    model_config = {"extra": "allow"}
    record_ext_id: str | None = None

    class Meta:
        model = Query
        fields = ["clinical_timestamp", "source_sequence", "external_id", "text"]

class QuerySchemaOut(ModelSchema):
    class Meta:
        model = Query
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "text", "record", "created_at", "updated_at"]

class RecordRevisionSchemaIn(ModelSchema):
    model_config = {"extra": "allow"}
    record_ext_id: str | None = None

    class Meta:
        model = RecordRevision
        fields = ["clinical_timestamp", "source_sequence", "external_id", "value"]

class RecordRevisionSchemaOut(ModelSchema):
    class Meta:
        model = RecordRevision
        fields = ["clinical_timestamp", "source_sequence", "offset_days", "id", "external_id", "value", "record", "created_at", "updated_at"]


# --- Endpoints ---


# L1: Study
@router.post("/studies", response=StudySchemaOut)
def sync_study(request, payload: StudySchemaIn):
    provider = getattr(request, 'provider', None)
    study, _ = Study.objects.update_or_create(external_id=payload.external_id, provider=provider, defaults={"clinical_timestamp": payload.clinical_timestamp, "source_sequence": payload.source_sequence, "name": payload.name})
    return study

@router.get("/studies", response=list[StudySchemaOut])
def list_studies(request):
    provider = getattr(request, 'provider', None)
    qs = Study.objects.all()
    if provider: qs = qs.filter(provider=provider)
    return qs

# L1: Site
@router.post("/sites", response=SiteSchemaOut)
def sync_site(request, payload: SiteSchemaIn):
    provider = getattr(request, 'provider', None)
    adapter = HierarchyAdapter(provider)
    parents = adapter.get_parents('Site', payload.model_dump())
    
    site, _ = Site.objects.update_or_create(
        external_id=payload.external_id, provider=provider, defaults={"clinical_timestamp": payload.clinical_timestamp, "source_sequence": payload.source_sequence, "name": payload.name, **parents}
    )
    return site

@router.get("/sites", response=list[SiteSchemaOut])
def list_sites(request):
    provider = getattr(request, 'provider', None)
    qs = Site.objects.select_related("study")
    if provider: qs = qs.filter(provider=provider)
    return qs

# L2: Subject
@router.post("/subjects", response=SubjectSchemaOut)
def sync_subject(request, payload: SubjectSchemaIn):
    provider = getattr(request, 'provider', None)
    adapter = HierarchyAdapter(provider)
    parents = adapter.get_parents('Subject', payload.model_dump())

    subject, _ = Subject.objects.update_or_create(
        external_id=payload.external_id, provider=provider, defaults={"clinical_timestamp": payload.clinical_timestamp, "source_sequence": payload.source_sequence, "name": payload.name, **parents}
    )
    return subject

@router.get("/subjects", response=list[SubjectSchemaOut])
def list_subjects(request):
    provider = getattr(request, 'provider', None)
    qs = Subject.objects.select_related("site")
    if provider: qs = qs.filter(provider=provider)
    return qs

# L2: Form
@router.post("/forms", response=FormSchemaOut)
def sync_form(request, payload: FormSchemaIn):
    provider = getattr(request, 'provider', None)
    adapter = HierarchyAdapter(provider)
    parents = adapter.get_parents('Form', payload.model_dump())

    form, _ = Form.objects.update_or_create(
        external_id=payload.external_id, provider=provider, defaults={"clinical_timestamp": payload.clinical_timestamp, "source_sequence": payload.source_sequence, "name": payload.name, **parents}
    )
    return form

@router.get("/forms", response=list[FormSchemaOut])
def list_forms(request):
    provider = getattr(request, 'provider', None)
    qs = Form.objects.select_related("study")
    if provider: qs = qs.filter(provider=provider)
    return qs

# L2: Interval
@router.post("/intervals", response=IntervalSchemaOut)
def sync_interval(request, payload: IntervalSchemaIn):
    provider = getattr(request, 'provider', None)
    adapter = HierarchyAdapter(provider)
    parents = adapter.get_parents('Interval', payload.model_dump())

    interval, _ = Interval.objects.update_or_create(
        external_id=payload.external_id, provider=provider, defaults={"clinical_timestamp": payload.clinical_timestamp, "source_sequence": payload.source_sequence, "name": payload.name, **parents}
    )
    return interval

@router.get("/intervals", response=list[IntervalSchemaOut])
def list_intervals(request):
    provider = getattr(request, 'provider', None)
    qs = Interval.objects.select_related("study")
    if provider: qs = qs.filter(provider=provider)
    return qs

# L3: Variable
@router.post("/variables", response=VariableSchemaOut)
def sync_variable(request, payload: VariableSchemaIn):
    provider = getattr(request, 'provider', None)
    adapter = HierarchyAdapter(provider)
    parents = adapter.get_parents('Variable', payload.model_dump())

    variable, _ = Variable.objects.update_or_create(
        external_id=payload.external_id, provider=provider, defaults={"clinical_timestamp": payload.clinical_timestamp, "source_sequence": payload.source_sequence, "name": payload.name, **parents}
    )
    return variable

@router.get("/variables", response=list[VariableSchemaOut])
def list_variables(request):
    provider = getattr(request, 'provider', None)
    qs = Variable.objects.select_related("form")
    if provider: qs = qs.filter(provider=provider)
    return qs

# L3: Visit
@router.post("/visits", response=VisitSchemaOut)
def sync_visit(request, payload: VisitSchemaIn):
    provider = getattr(request, 'provider', None)
    adapter = HierarchyAdapter(provider)
    parents = adapter.get_parents('Visit', payload.model_dump())

    visit, _ = Visit.objects.update_or_create(
        external_id=payload.external_id, provider=provider, defaults={"clinical_timestamp": payload.clinical_timestamp, "source_sequence": payload.source_sequence, **parents}
    )
    return visit

@router.get("/visits", response=list[VisitSchemaOut])
def list_visits(request):
    provider = getattr(request, 'provider', None)
    qs = Visit.objects.select_related("subject", "interval")
    if provider: qs = qs.filter(provider=provider)
    return qs

# L4: Record
@router.post("/records", response=RecordSchemaOut)
def sync_record(request, payload: RecordSchemaIn):
    provider = getattr(request, 'provider', None)
    adapter = HierarchyAdapter(provider)
    parents = adapter.get_parents('Record', payload.model_dump())

    record, _ = Record.objects.update_or_create(
        external_id=payload.external_id, provider=provider, defaults={"clinical_timestamp": payload.clinical_timestamp, "source_sequence": payload.source_sequence, "value": payload.value, **parents}
    )
    return record

@router.get("/records", response=list[RecordSchemaOut])
def list_records(request):
    provider = getattr(request, 'provider', None)
    qs = Record.objects.select_related("visit", "variable")
    if provider: qs = qs.filter(provider=provider)
    return qs

# L4: Coding
@router.post("/codings", response=CodingSchemaOut)
def sync_coding(request, payload: CodingSchemaIn):
    provider = getattr(request, 'provider', None)
    adapter = HierarchyAdapter(provider)
    parents = adapter.get_parents('Coding', payload.model_dump())

    coding, _ = Coding.objects.update_or_create(
        external_id=payload.external_id, provider=provider, defaults={"clinical_timestamp": payload.clinical_timestamp, "source_sequence": payload.source_sequence, "code": payload.code, **parents}
    )
    return coding

@router.get("/codings", response=list[CodingSchemaOut])
def list_codings(request):
    provider = getattr(request, 'provider', None)
    qs = Coding.objects.select_related("record")
    if provider: qs = qs.filter(provider=provider)
    return qs

# L4: Query
@router.post("/queries", response=QuerySchemaOut)
def sync_query(request, payload: QuerySchemaIn):
    provider = getattr(request, 'provider', None)
    adapter = HierarchyAdapter(provider)
    parents = adapter.get_parents('Query', payload.model_dump())

    query, _ = Query.objects.update_or_create(
        external_id=payload.external_id, provider=provider, defaults={"clinical_timestamp": payload.clinical_timestamp, "source_sequence": payload.source_sequence, "text": payload.text, **parents}
    )
    return query

@router.get("/queries", response=list[QuerySchemaOut])
def list_queries(request):
    provider = getattr(request, 'provider', None)
    qs = Query.objects.select_related("record")
    if provider: qs = qs.filter(provider=provider)
    return qs

# L4: RecordRevision
@router.post("/revisions", response=RecordRevisionSchemaOut)
def sync_revision(request, payload: RecordRevisionSchemaIn):
    provider = getattr(request, 'provider', None)
    adapter = HierarchyAdapter(provider)
    parents = adapter.get_parents('RecordRevision', payload.model_dump())

    revision, _ = RecordRevision.objects.update_or_create(
        external_id=payload.external_id, provider=provider, defaults={"clinical_timestamp": payload.clinical_timestamp, "source_sequence": payload.source_sequence, "value": payload.value, **parents}
    )
    return revision

@router.get("/revisions", response=list[RecordRevisionSchemaOut])
def list_revisions(request):
    provider = getattr(request, 'provider', None)
    qs = RecordRevision.objects.select_related("record")
    if provider: qs = qs.filter(provider=provider)
    return qs


@router.get("/export/cdisc")
def export_cdisc_package(request):
    # Check data-extraction privileges
    roles = getattr(request, 'user_roles', [])
    has_privilege = any(r in str(roles).lower() for r in ['export', 'extractor', 'cdisc'])
    if not (has_privilege or request.user.is_staff or request.user.is_superuser):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Missing data-extraction privileges")
    return generate_cdisc_export(request)
