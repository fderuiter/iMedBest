# ruff: noqa: RUF012, ERA001

from django.shortcuts import get_object_or_404
from ninja import ModelSchema, Router

from .models import Site, Study, Subject

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


# --- Endpoints ---

# L1: Study
@router.post("/studies", response=StudySchemaOut)
def sync_study(request, payload: StudySchemaIn):
    study, _ = Study.objects.update_or_create(external_id=payload.external_id, defaults={"name": payload.name})
    return study


@router.get("/studies", response=list[StudySchemaOut])
def list_studies(request):
    return Study.objects.all()


# L1: Site
@router.post("/sites", response=SiteSchemaOut)
def sync_site(request, payload: SiteSchemaIn):
    study = get_object_or_404(Study, external_id=payload.study_ext_id)
    site, _ = Site.objects.update_or_create(
        external_id=payload.external_id, defaults={"study": study, "name": payload.name}
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
        external_id=payload.external_id, defaults={"site": site, "name": payload.name}
    )
    return subject


@router.get("/subjects", response=list[SubjectSchemaOut])
def list_subjects(request):
    return Subject.objects.select_related("site").all()
