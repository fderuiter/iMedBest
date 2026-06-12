# ruff: noqa: ERA001
import json
import logging

import ninja.orm
import ninja.schema
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from ninja import ModelSchema, Router
from ninja.security import APIKeyHeader, HttpBearer
from pydantic.alias_generators import to_camel

from clinical.storage import get_storage_adapter
from clinical.tasks import process_direct_data_job

ninja.schema.Schema.model_config["alias_generator"] = to_camel
ninja.schema.Schema.model_config["populate_by_name"] = True
ninja.orm.ModelSchema.model_config["alias_generator"] = to_camel
ninja.orm.ModelSchema.model_config["populate_by_name"] = True


class JWTBearer(HttpBearer):
    def authenticate(self, request, token):
        from ninja.errors import HttpError

        from users.jwt import decode_jwt_token

        studyKey = request.headers.get("studyKey") or request.GET.get("studyKey")
        siteKey = request.headers.get("siteKey") or request.GET.get("siteKey")
        provider_id = request.headers.get("X-Provider")

        if not studyKey and hasattr(request, "resolver_match") and request.resolver_match:
            studyKey = request.resolver_match.kwargs.get("studyKey")

        if not studyKey and not siteKey:
            raise HttpError(400, "Missing required tenant context identifier: studyKey or siteKey")

        if not provider_id:
            raise HttpError(400, "Missing valid provider context")

        user = decode_jwt_token(token)
        if user:
            from clinical.models import Provider

            try:
                provider = Provider.objects.get(id=provider_id)
            except (Provider.DoesNotExist, ValueError):
                raise HttpError(400, "Invalid provider context") from None

            request.user = user
            request.studyKey = studyKey
            request.siteKey = siteKey
            request.provider = provider
            # Assign user_roles needed for export to users authenticated via JWT
            # In a full Entra setup, this would map groups/roles from the token
            # For now, give them "extractor" role so CDISC export isn't totally blocked
            request.user_roles = ["extractor"]
            return token
        return None


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
    ValidationResult,
    ValidationRule,
    Variable,
    Visit,
)
from .schemas import SyncJobRequest, SyncJobResponse


class IMednetAPIAuth(APIKeyHeader):
    param_name = "x-api-key"

    def authenticate(self, request, key):
        security_key = request.headers.get("x-imn-security-key")

        if key and security_key:
            studyKey = request.headers.get("studyKey") or request.GET.get("studyKey")
            siteKey = request.headers.get("siteKey") or request.GET.get("siteKey")
            provider_id = request.headers.get("X-Provider")

            if not studyKey and hasattr(request, "resolver_match") and request.resolver_match:
                studyKey = request.resolver_match.kwargs.get("studyKey")

            if not provider_id:
                from ninja.errors import HttpError

                raise HttpError(400, "Missing valid provider context")

            from clinical.models import Provider

            try:
                provider = Provider.objects.get(id=provider_id)
            except (Provider.DoesNotExist, ValueError):
                from ninja.errors import HttpError

                raise HttpError(400, "Invalid provider context") from None

            # We don't mandate studyKey for every single request in auth,
            # but if it's missing and we need it, the endpoint will fail or return empty.
            # However, for external persona, studyKey is usually in the URL.

            User = get_user_model()
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                user, _ = User.objects.get_or_create(username="external_spec_user", defaults={"is_staff": True})

            request.user = user
            request.studyKey = studyKey
            request.siteKey = siteKey
            request.provider = provider
            request.user_roles = ["extractor"]
            request.auth_method = "SpecCompliant"
            return key
        return None


def check_write_allowed(request):
    from ninja.errors import HttpError

    if getattr(request, "auth_method", "") == "SpecCompliant" or "/v1/" in request.path:
        raise HttpError(405, "Method Not Allowed")
    if not getattr(request, "provider", None):
        raise HttpError(400, "Missing valid provider context")


router = Router(auth=[JWTBearer(), IMednetAPIAuth()], by_alias=True)

logger = logging.getLogger(__name__)

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


class QuerySchemaIn(ModelSchema):
    record_ext_id: str
    status: str | None = "OPEN"

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


from typing import Any

from django.core.exceptions import PermissionDenied


def _queue_single_task(request, entity_type: str, payload_obj) -> tuple[int, Any]:
    if not (request.user.is_staff or request.user.is_superuser):
        from users.models import SiteMembership

        if not SiteMembership.objects.filter(user=request.user, role="site_investigator").exists():
            raise PermissionDenied("Clinical Auditors have read-only access.")

    from django.db import transaction

    from clinical.adapter import MultiVendorAdapter

    payload_dict = json.loads(payload_obj.model_dump_json(by_alias=False))
    provider = getattr(request, "provider", None)
    adapter = MultiVendorAdapter(provider)

    try:
        with transaction.atomic():
            job = SyncJob.objects.create(user=request.user, provider=provider, status="PROCESSING")
            task = SyncTask.objects.create(
                job=job,
                entity_type=entity_type,
                payload=payload_dict,
                status="PROCESSING",
            )
            result = adapter.sync_entity(request, entity_type, payload_dict)
            if isinstance(result, tuple) and len(result) == 2 and result[0] == 202:
                task.status = "BUFFERED"
                job.status = "PROCESSING"  # Job stays processing until orphan resolved
            else:
                task.status = "COMPLETED"
                job.status = "COMPLETED"
            task.save(update_fields=["status"])
            job.save(update_fields=["status"])

        from clinical.tasks import run_validation_for_job

        run_validation_for_job.delay(job.id)

        status_url = f"/api/clinical/sync-jobs/{job.id}"
        return 200, SyncJobResponse(job_id=job.id, status=job.status, message="Sync job queued", status_url=status_url)
    except Exception as e:
        return 400, {"message": f"Sync failed. No data was saved. Error: {e!s}"}


def mask_pii_for_user(request, data):
    user = getattr(request, "user", None)
    can_view = False
    if user and user.is_authenticated:
        if user.is_staff or user.is_superuser or user.has_perm("users.view_pii") or user.has_perm("clinical.view_pii"):
            can_view = True
        else:
            # Also check roles if applicable
            roles = getattr(request, "user_roles", [])
            if "view_pii" in str(roles).lower():
                can_view = True

    if can_view:
        return data

    for obj in data:
        study = obj.get_study()
        if study and getattr(study, "pii_masking_enabled", False):
            for field in getattr(obj, "pii_fields", []):
                val = getattr(obj, field, None)
                if val:
                    setattr(obj, field, "[REDACTED]")
    return data


# --- Endpoints ---


from .graph import get_provider_dependencies, topological_sort_entities


@router.get("/fhir/{resource_type}")
def get_fhir_resource(request, resource_type: str, subject: str = None):
    from ninja.errors import HttpError
    import requests
    from clinical.adapter import MultiVendorAdapter

    provider = getattr(request, "provider", None)
    if not provider:
        raise HttpError(400, "Missing valid provider context")

    if not provider.api_endpoint:
        raise HttpError(400, "Provider has no API endpoint configured")

    params = {}
    if subject:
        params["subject"] = subject

    try:
        url = f"{provider.api_endpoint}/{resource_type}"
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        raise HttpError(502, f"Failed to fetch data from provider: {e}")

    adapter = MultiVendorAdapter(provider)
    fhir_resources = []
    
    items = data if isinstance(data, list) else [data]
    
    # Try to reverse-map FHIR resource to internal raw type to properly map payload keys
    # or rely on adapter's mapping. We just use the resource_type as raw_type fallback.
    raw_type_map = {
        "Patient": "Subject",
        "Observation": "Record",
        "MedicationStatement": "Record"
    }
    raw_type = raw_type_map.get(resource_type, resource_type)

    for item in items:
        fhir_res = adapter.to_fhir(raw_type, item, fhir_resource_type=resource_type)
        if fhir_res:
            fhir_resources.append(fhir_res)

    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [{"resource": r} for r in fhir_resources]
    }


@router.post("/sync-jobs", response={200: SyncJobResponse, 400: dict})
def create_sync_job(request, payload: SyncJobRequest, studyKey: str | None = None):
    check_write_allowed(request)
    if not (request.user.is_staff or request.user.is_superuser):
        from users.models import SiteMembership

        if not SiteMembership.objects.filter(user=request.user, role="site_investigator").exists():
            raise PermissionDenied("Clinical Auditors have read-only access.")

    from django.db import transaction

    provider = getattr(request, "provider", None)

    # Perform topological sort of the entity types to resolve dynamic execution order
    sorted_entities = topological_sort_entities(payload.entities, provider)

    # Validate entity types
    valid_entity_types = {
        "Study",
        "Site",
        "Form",
        "Interval",
        "Subject",
        "Variable",
        "Visit",
        "Record",
        "Coding",
        "Query",
        "RecordRevision",
    }
    for entity in sorted_entities:
        if entity.entity_type not in valid_entity_types:
            return 400, {"message": f"Sync failed. Error: Unknown entity type: {entity.entity_type}"}

    try:
        with transaction.atomic():
            job = SyncJob.objects.create(user=request.user, provider=provider, status="PENDING")

            if len(payload.entities) > 2000:
                adapter = get_storage_adapter()
                raw_data_list = []
                for e in payload.entities:
                    e_dict = e.model_dump()
                    # Metadata stripping during file generation to avoid middleware bottlenecks
                    e_dict.get("payload", {}).pop("metadata", None)
                    raw_data_list.append(e_dict)

                try:
                    raw_data = json.dumps(raw_data_list)
                    job.file_path = adapter.save(f"sync_job_{job.id}.json", raw_data, namespace="sync_jobs")
                    job.save(update_fields=["file_path"])
                    process_direct_data_job.delay(job.id)
                except Exception as e:
                    logger.error(f"Failed to process and save bulk sync payload for job {job.id}: {e}", exc_info=True)
                    job.status = "FAILED"
                    job.save(update_fields=["status"])
            else:
                # Create tasks, and map their temporary IDs to set dependencies
                task_objects = []
                entity_type_to_task = {}
                for entity in sorted_entities:
                    task = SyncTask(
                        job=job,
                        entity_type=entity.entity_type,
                        payload=entity.payload,
                        status="PENDING",
                    )
                    task.save()
                    task_objects.append(task)
                    # Keep a list of tasks per entity type to resolve dependencies
                    entity_type_to_task.setdefault(entity.entity_type, []).append(task)

                # Assign DAG dependencies dynamically based on Provider definition
                dependencies_map = get_provider_dependencies(provider)
                for task in task_objects:
                    parent_types = dependencies_map.get(task.entity_type, [])
                    for parent_type in parent_types:
                        parent_tasks = entity_type_to_task.get(parent_type, [])
                        for pt in parent_tasks:
                            task.dependencies.add(pt)

                # Trigger celery orchestrator
                from clinical.tasks import orchestrate_sync_job

                orchestrate_sync_job.delay(job.id)

        status_url = f"/api/clinical/sync-jobs/{job.id}"
        return 200, SyncJobResponse(job_id=job.id, status=job.status, message="Sync job queued", status_url=status_url)
    except Exception as e:
        return 400, {"message": f"Sync failed. Error: {e!s}"}


@router.get("/sync-jobs/{job_id}", response=JobStatusSchemaOut)
def get_sync_job(request, job_id: str, studyKey: str | None = None):
    return get_object_or_404(SyncJob, id=job_id, user=request.user)


# L1: Study
@router.post("/studies", response={200: SyncJobResponse, 400: dict})
def api_sync_study(request, payload: StudySchemaIn, studyKey: str | None = None):
    check_write_allowed(request)
    return _queue_single_task(request, "Study", payload)


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
def list_studies(request, studyKey: str | None = None):
    qs = get_accessible_studies(request)
    return mask_pii_for_user(request, list(qs))


# L1: Site
@router.post("/sites", response={200: SyncJobResponse, 400: dict})
def api_sync_site(request, payload: SiteSchemaIn, studyKey: str | None = None):
    check_write_allowed(request)
    return _queue_single_task(request, "Site", payload)


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
def list_sites(request, studyKey: str | None = None):
    qs = get_accessible_sites(request).select_related("study")
    return mask_pii_for_user(request, list(qs))


# L2: Subject
@router.post("/subjects", response={200: SyncJobResponse, 400: dict})
def api_sync_subject(request, payload: SubjectSchemaIn, studyKey: str | None = None):
    check_write_allowed(request)
    return _queue_single_task(request, "Subject", payload)


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
def list_subjects(request, studyKey: str | None = None):
    qs = get_accessible_subjects(request).select_related("site")
    return mask_pii_for_user(request, list(qs))


# L2: Form
@router.post("/forms", response={200: SyncJobResponse, 400: dict})
def api_sync_form(request, payload: FormSchemaIn, studyKey: str | None = None):
    check_write_allowed(request)
    return _queue_single_task(request, "Form", payload)


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
def list_forms(request, studyKey: str | None = None):
    qs = Form.objects.filter(study__in=get_accessible_studies(request)).select_related("study")
    return mask_pii_for_user(request, list(qs))


# L2: Interval
@router.post("/intervals", response={200: SyncJobResponse, 400: dict})
def api_sync_interval(request, payload: IntervalSchemaIn, studyKey: str | None = None):
    check_write_allowed(request)
    return _queue_single_task(request, "Interval", payload)


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
def list_intervals(request, studyKey: str | None = None):
    qs = Interval.objects.filter(study__in=get_accessible_studies(request)).select_related("study")
    return mask_pii_for_user(request, list(qs))


# L3: Variable
@router.post("/variables", response={200: SyncJobResponse, 400: dict})
def api_sync_variable(request, payload: VariableSchemaIn, studyKey: str | None = None):
    check_write_allowed(request)
    return _queue_single_task(request, "Variable", payload)


def sync_variable(request, payload: VariableSchemaIn):
    form = (
        Form.objects.filter(study__in=get_accessible_studies(request)).filter(external_id=payload.form_ext_id).first()
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
def list_variables(request, studyKey: str | None = None):
    qs = Variable.objects.filter(form__study__in=get_accessible_studies(request)).select_related("form")
    return mask_pii_for_user(request, list(qs))


# L3: Visit
@router.post("/visits", response={200: SyncJobResponse, 400: dict})
def api_sync_visit(request, payload: VisitSchemaIn, studyKey: str | None = None):
    check_write_allowed(request)
    return _queue_single_task(request, "Visit", payload)


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
def list_visits(request, studyKey: str | None = None):
    qs = Visit.objects.filter(subject__in=get_accessible_subjects(request)).select_related("subject", "interval")
    return mask_pii_for_user(request, list(qs))


# L4: Record
@router.post("/records", response={200: SyncJobResponse, 400: dict})
def api_sync_record(request, payload: RecordSchemaIn, studyKey: str | None = None):
    check_write_allowed(request)
    return _queue_single_task(request, "Record", payload)


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
def list_records(request, studyKey: str | None = None):
    return Record.objects.filter(visit__subject__in=get_accessible_subjects(request)).select_related(
        "visit", "variable"
    )


# L4: Coding
@router.post("/codings", response={200: SyncJobResponse, 400: dict})
def api_sync_coding(request, payload: CodingSchemaIn, studyKey: str | None = None):
    check_write_allowed(request)
    return _queue_single_task(request, "Coding", payload)


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
def list_codings(request, studyKey: str | None = None):
    qs = Coding.objects.filter(record__visit__subject__in=get_accessible_subjects(request)).select_related("record")
    return mask_pii_for_user(request, list(qs))


# L4: Query
@router.post("/queries", response={200: SyncJobResponse, 400: dict})
def api_sync_query(request, payload: QuerySchemaIn, studyKey: str | None = None):
    check_write_allowed(request)
    return _queue_single_task(request, "Query", payload)


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

        # Bi-directional state sync for validation
        if query.status == "RESOLVED":
            from clinical.models import ValidationResult

            ValidationResult.objects.filter(query=query).update(passed=True)
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
def list_queries(request, studyKey: str | None = None):
    qs = Query.objects.filter(record__visit__subject__in=get_accessible_subjects(request)).select_related("record")
    return mask_pii_for_user(request, list(qs))


@router.patch("/queries/{query_id}", response=QuerySchemaOut)
def update_query(request, query_id: int, payload: QueryUpdateIn, studyKey: str | None = None):
    check_write_allowed(request)
    query = Query.objects.get(id=query_id, record__visit__subject__in=get_accessible_subjects(request))
    query.previous_status = query.status
    query.status = payload.status
    query.sync_status = "PENDING"
    query.save(update_fields=["status", "previous_status", "sync_status", "updated_at"])

    if query.status == "RESOLVED":
        from clinical.models import ValidationResult

        ValidationResult.objects.filter(query=query).update(passed=True)

    from django.core.cache import cache
    from django.utils import timezone

    cache.set("last_query_activity_time", timezone.now(), timeout=86400)

    # Trigger background sync to upstream EDC
    from clinical.tasks import sync_query_upstream

    sync_query_upstream.delay(query.id)

    return mask_pii_for_user(request, [query])[0]


# L4: RecordRevision
@router.post("/revisions", response={200: SyncJobResponse, 400: dict})
def api_sync_revision(request, payload: RecordRevisionSchemaIn, studyKey: str | None = None):
    check_write_allowed(request)
    return _queue_single_task(request, "RecordRevision", payload)


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
def list_revisions(request, studyKey: str | None = None):
    return RecordRevision.objects.filter(record__visit__subject__in=get_accessible_subjects(request)).select_related(
        "record"
    )


@router.get("/export/cdisc")
def export_cdisc_package(request, studyKey: str | None = None):
    # Check data-extraction privileges
    roles = getattr(request, "user_roles", [])
    has_privilege = any(r in str(roles).lower() for r in ["export", "extractor", "cdisc"])
    if not (has_privilege or request.user.is_staff or request.user.is_superuser):
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Missing data-extraction privileges")

    from clinical.models import ExportJob
    from clinical.tasks import export_cdisc_task

    job = ExportJob.objects.create(user=request.user)
    # Trigger background task
    export_cdisc_task.delay(job.id)

    return {"message": "Export job started.", "job_id": job.id}


@router.get("/export/cdisc/{job_id}/download")
def download_cdisc_package(request, job_id: int):
    from django.http import Http404, HttpResponse

    from clinical.models import ExportJob
    from clinical.storage import get_storage_adapter

    try:
        job = ExportJob.objects.get(id=job_id)
    except ExportJob.DoesNotExist as exc:
        raise Http404("Job not found") from exc

    adapter = get_storage_adapter()
    phi = job.contains_phi
    if job.status != "COMPLETED" or not job.file_path or not adapter.exists(job.file_path, contains_phi=phi):
        return HttpResponse("Job not completed or file missing.", status=400)

    response = HttpResponse(adapter.open(job.file_path, "rb", contains_phi=phi), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="cdisc_export.zip"'
    return response


class BufferedOrphanSchemaOut(ModelSchema):
    class Meta:
        model = BufferedOrphan
        fields = ["id", "entity_type", "missing_parent_id", "created_at"]


@router.get("/orphans", response=list[BufferedOrphanSchemaOut])
def list_orphans(request, studyKey: str | None = None):
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
            logger.warning("Orphan reprocessing failed for parent %s: %s", parent_external_id, e)


def _reprocess_orphan(orphan):
    req = type("DummyRequest", (object,), {"user": orphan.user, "provider": orphan.provider, "user_roles": ["cdisc"]})()

    adapter = MultiVendorAdapter(orphan.provider)
    result = adapter.sync_entity(req, orphan.entity_type, orphan.payload)

    if not (isinstance(result, tuple) and len(result) == 2 and result[0] == 202):
        from audit.models import AuditLog

        from .models import SyncTask

        tasks = SyncTask.objects.filter(status="BUFFERED", entity_type=orphan.entity_type)
        for task in tasks:
            if task.payload == orphan.payload:
                task.status = "COMPLETED"
                task.save(update_fields=["status"])
                AuditLog.objects.create(
                    action="UPDATE",
                    model_name="SyncTask",
                    object_id=str(task.id),
                    user=orphan.user,
                    changes={
                        "status": ["BUFFERED", "COMPLETED"],
                        "resolving_parent_record": orphan.missing_parent_id,
                    },
                )
                logger.info(
                    "Transitioned buffered task %s to COMPLETED via parent %s", task.id, orphan.missing_parent_id
                )

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
def delete_entity(request, entity_plural: str, external_id: str, studyKey: str | None = None):
    check_write_allowed(request)
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
def list_trash(request, studyKey: str | None = None):
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
def restore_entity(request, entity_type: str, external_id: str, studyKey: str | None = None):
    check_write_allowed(request)
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


class StripSyncMetadataMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if hasattr(request, "auth_method") and request.auth_method == "SpecCompliant":
            # or we can check path: "/v1/edc/" in request.path
            if getattr(response, "streaming", False):
                return response

            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                try:
                    data = json.loads(response.content)
                    fields_to_remove = [
                        "source_sequence",
                        "offset_days",
                        "sync_status",
                        "last_sync_error",
                        "clinical_timestamp",
                    ]

                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                for f in fields_to_remove:
                                    item.pop(f, None)
                    elif isinstance(data, dict):
                        for f in fields_to_remove:
                            data.pop(f, None)

                    response.content = json.dumps(data)
                    response["Content-Length"] = str(len(response.content))
                except Exception:  # noqa: S110
                    pass
        return response


@router.get("/validation/dashboard-summary")
def get_validation_dashboard(request, studyKey: str | None = None):
    # Filter by provider to prevent cross-tenant data leaks
    provider = getattr(request, "provider", None)
    if not provider:
        from ninja.errors import HttpError

        raise HttpError(400, "Missing provider context")

    # Start with tenant-scoped queryset filtering by provider via job
    qs = ValidationResult.objects.filter(job__provider=provider)

    # Further filter by study if provided
    if studyKey:
        # Filter validation results to those whose job's records/entities belong to the specified study
        # Since ValidationResult -> job -> entities can span multiple models,
        # we'll need to find a path. For now, filter by checking if any record in the job belongs to that study.
        # A more robust approach would be to add a study field to SyncJob or ValidationResult.
        # For this fix, we'll filter by checking records via the query relationship
        qs = qs.filter(query__record__visit__subject__site__study__key=studyKey)

    total_checks = qs.count()
    if total_checks == 0:
        return {"passed_percentage": 100.0, "total_checks": 0, "failed_checks": 0, "passed_checks": 0}
    passed_checks = qs.filter(passed=True).count()
    failed_checks = total_checks - passed_checks
    passed_percentage = (passed_checks / total_checks) * 100.0

    return {
        "passed_percentage": round(passed_percentage, 2),
        "total_checks": total_checks,
        "failed_checks": failed_checks,
        "passed_checks": passed_checks,
    }


class ValidationRuleSchemaIn(ModelSchema):
    class Meta:
        model = ValidationRule
        fields = ["name", "description", "rule_dsl", "is_active", "version"]


class ValidationRuleSchemaOut(ModelSchema):
    class Meta:
        model = ValidationRule
        fields = ["id", "name", "description", "rule_dsl", "is_active", "version", "created_at", "updated_at"]


@router.post("/validation-rules", response=ValidationRuleSchemaOut)
def create_validation_rule(request, payload: ValidationRuleSchemaIn):
    # Enforce write protection to prevent bypass via SpecCompliant auth
    check_write_allowed(request)

    if not (request.user.is_staff or request.user.is_superuser):
        from ninja.errors import HttpError

        raise HttpError(403, "Admin access required to create validation rules.")

    rule = ValidationRule.objects.create(
        name=payload.name,
        description=payload.description,
        rule_dsl=payload.rule_dsl,
        is_active=payload.is_active,
        version=payload.version,
    )
    return rule


@router.get("/validation-rules", response=list[ValidationRuleSchemaOut])
def list_validation_rules(request):
    return ValidationRule.objects.all()
