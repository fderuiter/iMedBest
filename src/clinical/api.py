# ruff: noqa: RUF012, ERA001

from django.db import transaction
from django.shortcuts import get_object_or_404
from ninja import ModelSchema, Router

from users.auth import OIDCBearer

from .export import generate_cdisc_export
from .models import Coding, Form, Interval, Query, Record, RecordRevision, Site, Study, Subject, Variable, Visit

router = Router(auth=OIDCBearer())

# --- Schemas ---


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


# L1: Study
@router.post("/studies", response=list[StudySchemaOut] | StudySchemaOut)
def sync_study(request, payload: list[StudySchemaIn] | StudySchemaIn):
    """Synchronizes data. This endpoint is transactional; if a batch is provided and one fails, the entire batch is rolled back."""
    is_list = isinstance(payload, list)
    items = payload if is_list else [payload]
    results = []
    with transaction.atomic():
        for item in items:
            defaults = {
                "clinical_timestamp": item.clinical_timestamp, 
                "source_sequence": item.source_sequence, 
                "name": item.name,
                "updated_by": request.user
            }
            study, _ = Study.objects.update_or_create(
                external_id=item.external_id, 
                defaults=defaults,
                create_defaults={**defaults, "created_by": request.user}
            )
            results.append(study)
    return results if is_list else results[0]


@router.get("/studies", response=list[StudySchemaOut])
def list_studies(request):
    return get_accessible_studies(request.user)


# L1: Site
@router.post("/sites", response=list[SiteSchemaOut] | SiteSchemaOut)
def sync_site(request, payload: list[SiteSchemaIn] | SiteSchemaIn):
    """Synchronizes data. This endpoint is transactional; if a batch is provided and one fails, the entire batch is rolled back."""
    is_list = isinstance(payload, list)
    items = payload if is_list else [payload]
    results = []
    with transaction.atomic():
        for item in items:
            study = get_object_or_404(get_accessible_studies(request.user), external_id=item.study_ext_id)
            defaults = {
                "clinical_timestamp": item.clinical_timestamp, 
                "source_sequence": item.source_sequence, 
                "study": study, 
                "name": item.name,
                "updated_by": request.user
            }
            site, _ = Site.objects.update_or_create(
                external_id=item.external_id, 
                defaults=defaults,
                create_defaults={**defaults, "created_by": request.user}
            )
            results.append(site)
    return results if is_list else results[0]


@router.get("/sites", response=list[SiteSchemaOut])
def list_sites(request):
    return get_accessible_sites(request.user).select_related("study")


# L2: Subject
@router.post("/subjects", response=list[SubjectSchemaOut] | SubjectSchemaOut)
def sync_subject(request, payload: list[SubjectSchemaIn] | SubjectSchemaIn):
    """Synchronizes data. This endpoint is transactional; if a batch is provided and one fails, the entire batch is rolled back."""
    is_list = isinstance(payload, list)
    items = payload if is_list else [payload]
    results = []
    with transaction.atomic():
        for item in items:
            site = get_object_or_404(get_accessible_sites(request.user), external_id=item.site_ext_id)
            defaults = {
                "clinical_timestamp": item.clinical_timestamp, 
                "source_sequence": item.source_sequence, 
                "site": site, 
                "name": item.name,
                "updated_by": request.user
            }
            subject, _ = Subject.objects.update_or_create(
                external_id=item.external_id, 
                defaults=defaults,
                create_defaults={**defaults, "created_by": request.user}
            )
            results.append(subject)
    return results if is_list else results[0]


@router.get("/subjects", response=list[SubjectSchemaOut])
def list_subjects(request):
    return get_accessible_subjects(request.user).select_related("site")


# L2: Form
@router.post("/forms", response=list[FormSchemaOut] | FormSchemaOut)
def sync_form(request, payload: list[FormSchemaIn] | FormSchemaIn):
    """Synchronizes data. This endpoint is transactional; if a batch is provided and one fails, the entire batch is rolled back."""
    is_list = isinstance(payload, list)
    items = payload if is_list else [payload]
    results = []
    with transaction.atomic():
        for item in items:
            study = get_object_or_404(get_accessible_studies(request.user), external_id=item.study_ext_id)
            defaults = {
                "clinical_timestamp": item.clinical_timestamp, 
                "source_sequence": item.source_sequence, 
                "study": study, 
                "name": item.name,
                "updated_by": request.user
            }
            form, _ = Form.objects.update_or_create(
                external_id=item.external_id, 
                defaults=defaults,
                create_defaults={**defaults, "created_by": request.user}
            )
            results.append(form)
    return results if is_list else results[0]


@router.get("/forms", response=list[FormSchemaOut])
def list_forms(request):
    return Form.objects.filter(study__in=get_accessible_studies(request.user)).select_related("study")


# L2: Interval
@router.post("/intervals", response=list[IntervalSchemaOut] | IntervalSchemaOut)
def sync_interval(request, payload: list[IntervalSchemaIn] | IntervalSchemaIn):
    """Synchronizes data. This endpoint is transactional; if a batch is provided and one fails, the entire batch is rolled back."""
    is_list = isinstance(payload, list)
    items = payload if is_list else [payload]
    results = []
    with transaction.atomic():
        for item in items:
            study = get_object_or_404(get_accessible_studies(request.user), external_id=item.study_ext_id)
            defaults = {
                "clinical_timestamp": item.clinical_timestamp, 
                "source_sequence": item.source_sequence, 
                "study": study, 
                "name": item.name,
                "updated_by": request.user
            }
            interval, _ = Interval.objects.update_or_create(
                external_id=item.external_id, 
                defaults=defaults,
                create_defaults={**defaults, "created_by": request.user}
            )
            results.append(interval)
    return results if is_list else results[0]


@router.get("/intervals", response=list[IntervalSchemaOut])
def list_intervals(request):
    return Interval.objects.filter(study__in=get_accessible_studies(request.user)).select_related("study")


# L3: Variable
@router.post("/variables", response=list[VariableSchemaOut] | VariableSchemaOut)
def sync_variable(request, payload: list[VariableSchemaIn] | VariableSchemaIn):
    """Synchronizes data. This endpoint is transactional; if a batch is provided and one fails, the entire batch is rolled back."""
    is_list = isinstance(payload, list)
    items = payload if is_list else [payload]
    results = []
    with transaction.atomic():
        for item in items:
            form = get_object_or_404(Form.objects.filter(study__in=get_accessible_studies(request.user)), external_id=item.form_ext_id)
            defaults = {
                "clinical_timestamp": item.clinical_timestamp, 
                "source_sequence": item.source_sequence, 
                "form": form, 
                "name": item.name,
                "updated_by": request.user
            }
            variable, _ = Variable.objects.update_or_create(
                external_id=item.external_id, 
                defaults=defaults,
                create_defaults={**defaults, "created_by": request.user}
            )
            results.append(variable)
    return results if is_list else results[0]


@router.get("/variables", response=list[VariableSchemaOut])
def list_variables(request):
    return Variable.objects.filter(form__study__in=get_accessible_studies(request.user)).select_related("form")


# L3: Visit
@router.post("/visits", response=list[VisitSchemaOut] | VisitSchemaOut)
def sync_visit(request, payload: list[VisitSchemaIn] | VisitSchemaIn):
    """Synchronizes data. This endpoint is transactional; if a batch is provided and one fails, the entire batch is rolled back."""
    is_list = isinstance(payload, list)
    items = payload if is_list else [payload]
    results = []
    with transaction.atomic():
        for item in items:
            subject = get_object_or_404(get_accessible_subjects(request.user), external_id=item.subject_ext_id)
            interval = get_object_or_404(Interval.objects.filter(study__in=get_accessible_studies(request.user)), external_id=item.interval_ext_id)
            defaults = {
                "clinical_timestamp": item.clinical_timestamp, 
                "source_sequence": item.source_sequence, 
                "subject": subject, 
                "interval": interval,
                "updated_by": request.user
            }
            visit, _ = Visit.objects.update_or_create(
                external_id=item.external_id, 
                defaults=defaults,
                create_defaults={**defaults, "created_by": request.user}
            )
            results.append(visit)
    return results if is_list else results[0]


@router.get("/visits", response=list[VisitSchemaOut])
def list_visits(request):
    return Visit.objects.filter(subject__in=get_accessible_subjects(request.user)).select_related("subject", "interval")


# L4: Record
@router.post("/records", response=list[RecordSchemaOut] | RecordSchemaOut)
def sync_record(request, payload: list[RecordSchemaIn] | RecordSchemaIn):
    """Synchronizes data. This endpoint is transactional; if a batch is provided and one fails, the entire batch is rolled back."""
    is_list = isinstance(payload, list)
    items = payload if is_list else [payload]
    results = []
    with transaction.atomic():
        for item in items:
            visit = get_object_or_404(Visit.objects.filter(subject__in=get_accessible_subjects(request.user)), external_id=item.visit_ext_id)
            variable = get_object_or_404(Variable.objects.filter(form__study__in=get_accessible_studies(request.user)), external_id=item.variable_ext_id)
            defaults = {
                "clinical_timestamp": item.clinical_timestamp, 
                "source_sequence": item.source_sequence, 
                "visit": visit, 
                "variable": variable, 
                "value": item.value,
                "updated_by": request.user
            }
            record, _ = Record.objects.update_or_create(
                external_id=item.external_id, 
                defaults=defaults,
                create_defaults={**defaults, "created_by": request.user}
            )
            results.append(record)
    return results if is_list else results[0]


@router.get("/records", response=list[RecordSchemaOut])
def list_records(request):
    return Record.objects.filter(visit__subject__in=get_accessible_subjects(request.user)).select_related("visit", "variable")


# L4: Coding
@router.post("/codings", response=list[CodingSchemaOut] | CodingSchemaOut)
def sync_coding(request, payload: list[CodingSchemaIn] | CodingSchemaIn):
    """Synchronizes data. This endpoint is transactional; if a batch is provided and one fails, the entire batch is rolled back."""
    is_list = isinstance(payload, list)
    items = payload if is_list else [payload]
    results = []
    with transaction.atomic():
        for item in items:
            record = get_object_or_404(Record.objects.filter(visit__subject__in=get_accessible_subjects(request.user)), external_id=item.record_ext_id)
            defaults = {
                "clinical_timestamp": item.clinical_timestamp, 
                "source_sequence": item.source_sequence, 
                "record": record, 
                "code": item.code,
                "updated_by": request.user
            }
            coding, _ = Coding.objects.update_or_create(
                external_id=item.external_id, 
                defaults=defaults,
                create_defaults={**defaults, "created_by": request.user}
            )
            results.append(coding)
    return results if is_list else results[0]


@router.get("/codings", response=list[CodingSchemaOut])
def list_codings(request):
    return Coding.objects.filter(record__visit__subject__in=get_accessible_subjects(request.user)).select_related("record")


# L4: Query
@router.post("/queries", response=list[QuerySchemaOut] | QuerySchemaOut)
def sync_query(request, payload: list[QuerySchemaIn] | QuerySchemaIn):
    """Synchronizes data. This endpoint is transactional; if a batch is provided and one fails, the entire batch is rolled back."""
    is_list = isinstance(payload, list)
    items = payload if is_list else [payload]
    results = []
    with transaction.atomic():
        for item in items:
            record = get_object_or_404(Record.objects.filter(visit__subject__in=get_accessible_subjects(request.user)), external_id=item.record_ext_id)
            defaults = {
                "clinical_timestamp": item.clinical_timestamp, 
                "source_sequence": item.source_sequence, 
                "record": record, 
                "text": item.text,
                "updated_by": request.user
            }
            query, _ = Query.objects.update_or_create(
                external_id=item.external_id, 
                defaults=defaults,
                create_defaults={**defaults, "created_by": request.user}
            )
            results.append(query)
    return results if is_list else results[0]


@router.get("/queries", response=list[QuerySchemaOut])
def list_queries(request):
    return Query.objects.filter(record__visit__subject__in=get_accessible_subjects(request.user)).select_related("record")


# L4: RecordRevision
@router.post("/revisions", response=list[RecordRevisionSchemaOut] | RecordRevisionSchemaOut)
def sync_revision(request, payload: list[RecordRevisionSchemaIn] | RecordRevisionSchemaIn):
    """Synchronizes data. This endpoint is transactional; if a batch is provided and one fails, the entire batch is rolled back."""
    is_list = isinstance(payload, list)
    items = payload if is_list else [payload]
    results = []
    with transaction.atomic():
        for item in items:
            record = get_object_or_404(Record.objects.filter(visit__subject__in=get_accessible_subjects(request.user)), external_id=item.record_ext_id)
            defaults = {
                "clinical_timestamp": item.clinical_timestamp, 
                "source_sequence": item.source_sequence, 
                "record": record, 
                "value": item.value,
                "updated_by": request.user
            }
            revision, _ = RecordRevision.objects.update_or_create(
                external_id=item.external_id, 
                defaults=defaults,
                create_defaults={**defaults, "created_by": request.user}
            )
            results.append(revision)
    return results if is_list else results[0]


@router.get("/revisions", response=list[RecordRevisionSchemaOut])
def list_revisions(request):
    return RecordRevision.objects.filter(record__visit__subject__in=get_accessible_subjects(request.user)).select_related("record")




@router.get("/export/cdisc")
def export_cdisc_package(request):
    # Check data-extraction privileges
    roles = getattr(request, 'user_roles', [])
    has_privilege = any(r in str(roles).lower() for r in ['export', 'extractor', 'cdisc'])
    if not (has_privilege or request.user.is_staff or request.user.is_superuser):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Missing data-extraction privileges")
    return generate_cdisc_export(request)
