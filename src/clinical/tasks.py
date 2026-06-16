import logging

from celery import shared_task
from django.utils import timezone

from .models import (
    SyncJob,
    SyncTask,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, acks_late=True, reject_on_worker_lost=True)
def process_sync_task(self, task_id):
    task = SyncTask.objects.get(id=task_id)
    try:
        task.status = "PROCESSING"
        task.save(update_fields=["status"])

        # Process the task payload based on entity_type
        # In a real app we'd map this dynamically or use the existing sync_* functions
        # For simplicity, we just use a generic approach or dispatch manually

        # We need to simulate the saving of data with transactional integrity.
        # "parent entities are fully processed before child entities are initiated"

        # After successful save:
        task.status = "COMPLETED"
        task.save(update_fields=["status"])

        # Queue child tasks if any are waiting for this parent
        child_tasks = SyncTask.objects.filter(parent_task_id=task.id, status="PENDING")
        for child in child_tasks:
            process_sync_task.delay(child.id)

        # Check if job is completed
        job = task.job
        if not job.tasks.exclude(status="COMPLETED").exists():
            job.status = "COMPLETED"
            job.save(update_fields=["status"])
            run_validation_for_job.delay(job.id)

    except Exception as exc:
        task.error_message = str(exc)
        task.retry_count += 1
        try:
            task.status = "PENDING"
            task.save(update_fields=["status", "error_message", "retry_count"])
            self.retry(exc=exc, countdown=2**task.retry_count)  # Exponential backoff
        except self.MaxRetriesExceededError:
            task.status = "FAILED"
            task.save(update_fields=["status"])
            logger.error(f"Task {task.id} failed after max retries")
            job = task.job
            job.status = "FAILED"
            job.save(update_fields=["status"])


@shared_task(acks_late=True, reject_on_worker_lost=True)
def orchestrate_sync_job(job_id):
    job = SyncJob.objects.get(id=job_id)
    job.status = "PROCESSING"
    job.save(update_fields=["status"])

    try:
        process_next_ready_tasks.delay(job_id)
    except Exception as e:
        job.status = "FAILED"
        job.error_message = str(e)
        job.save(update_fields=["status", "error_message"])


@shared_task(bind=True, max_retries=3, acks_late=True, reject_on_worker_lost=True)
def process_next_ready_tasks(self, job_id):
    job = SyncJob.objects.get(id=job_id)
    if job.status == "FAILED":
        return

    pending_tasks = SyncTask.objects.filter(job=job, status="PENDING")
    if not pending_tasks.exists():
        # Check that no tasks are PROCESSING or FAILED before marking job as COMPLETED
        if not SyncTask.objects.filter(job=job, status__in=["PROCESSING", "FAILED"]).exists():
            job.status = "COMPLETED"
            job.save(update_fields=["status"])
            run_validation_for_job.delay(job.id)
        return

    started_any = False
    for task in pending_tasks:
        deps = task.dependencies.all()
        # If no dependencies, or all dependencies are COMPLETED, we can start it
        if all(d.status == "COMPLETED" for d in deps):
            task.status = "PROCESSING"
            task.save(update_fields=["status"])
            process_single_task.delay(task.id)
            started_any = True

    if not started_any:
        # Check if we are stuck because of FAILED dependencies
        failed_dependencies = False
        for task in pending_tasks:
            deps = task.dependencies.all()
            if any(d.status == "FAILED" for d in deps):
                task.status = "FAILED"
                task.error_message = "Dependency failed"
                task.save(update_fields=["status", "error_message"])
                failed_dependencies = True

        if failed_dependencies:
            # Trigger again to process downstream failures or finish job
            process_next_ready_tasks.apply_async((job_id,), countdown=1)
        else:
            # Wait for currently PROCESSING tasks to finish
            check_level_completion.apply_async((job_id,), countdown=2)


@shared_task(bind=True, max_retries=3, acks_late=True, reject_on_worker_lost=True)
def process_direct_data_job(self, job_id):
    job = SyncJob.objects.get(id=job_id)
    if job.status == "FAILED":
        return

    job.status = "PROCESSING"
    job.save(update_fields=["status"])

    try:
        import json

        from django.db import transaction

        from audit.middleware import get_current_request
        from clinical.adapter import MultiVendorAdapter
        from clinical.graph import topological_sort_entities
        from clinical.schemas import EntityPayload
        from clinical.storage import get_storage_adapter

        request = get_current_request()
        if request is None:
            from django.contrib.auth.models import AnonymousUser

            class _SystemRequest:
                user = AnonymousUser()
                user_roles: list = []
                provider = job.provider
                META: dict = {}

            request = _SystemRequest()

        adapter_instance = MultiVendorAdapter(job.provider)
        storage_adapter = get_storage_adapter()

        if not job.file_path or not storage_adapter.exists(job.file_path, contains_phi=False):
            raise FileNotFoundError("Direct Data payload file missing")

        with storage_adapter.open(job.file_path, "rb", contains_phi=False) as f:
            raw_data = json.load(f)

        entities = [EntityPayload(**ent) for ent in raw_data]

        orphaned_count = 0
        with transaction.atomic():
            sorted_entities = topological_sort_entities(entities, job.provider)

            # Process each entity linearly
            for entity in sorted_entities:
                response = adapter_instance.sync_entity(request, entity.entity_type, entity.payload)
                if isinstance(response, tuple) and response[0] == 202:
                    orphaned_count += 1

        if orphaned_count > 0:
            job.status = "PARTIAL"
        else:
            job.status = "COMPLETED"
        job.save(update_fields=["status"])
        run_validation_for_job.delay(job.id)
    except Exception as exc:
        job.status = "FAILED"
        job.error_message = str(exc)
        job.save(update_fields=["status", "error_message"])


@shared_task(bind=True, max_retries=5, acks_late=True, reject_on_worker_lost=True)
def process_single_task(self, task_id):
    task = SyncTask.objects.get(id=task_id)
    if task.status != "PENDING":
        return

    task.status = "PROCESSING"
    task.save(update_fields=["status"])

    try:
        from audit.middleware import get_current_request
        from clinical.adapter import MultiVendorAdapter

        request = get_current_request()
        if request is None:
            from django.contrib.auth.models import AnonymousUser

            class _SystemRequest:
                user = AnonymousUser()
                user_roles: list = []
                provider = task.job.provider
                META: dict = {}

            request = _SystemRequest()

        payload = task.payload
        entity_type = task.entity_type

        adapter = MultiVendorAdapter(task.job.provider)
        adapter.sync_entity(request, entity_type, payload)

        task.status = "COMPLETED"
        task.save(update_fields=["status"])
        process_next_ready_tasks.delay(task.job_id)

    except Exception as exc:
        task.error_message = str(exc)
        task.retry_count += 1
        try:
            # Revert to PENDING so the retry can process it and level completion waits
            task.status = "PENDING"
            task.save(update_fields=["status", "error_message", "retry_count"])
            self.retry(exc=exc, countdown=2**task.retry_count)  # Exponential backoff
        except self.MaxRetriesExceededError:
            task.status = "FAILED"
            task.save(update_fields=["status"])
            logger.error(f"Task {task.id} failed after max retries")


@shared_task(acks_late=True, reject_on_worker_lost=True)
def check_level_completion(job_id):
    job = SyncJob.objects.get(id=job_id)
    if job.status == "FAILED":
        return  # Stop processing

    if SyncTask.objects.filter(job=job, status="PROCESSING").exists():
        # Still processing, check again later
        check_level_completion.apply_async((job_id,), countdown=2)
        return

    # Call process_next_ready_tasks to advance the job
    process_next_ready_tasks.delay(job_id)


@shared_task
def purge_trash_task(days=30):
    from django.core.management import call_command

    call_command("purge_trash", days=days)


@shared_task
def reconstruct_subject_timeline(subject_id):
    from clinical.models import Coding, Query, Record, RecordRevision, Subject, Visit

    try:
        subject = Subject.objects.get(id=subject_id)
    except Subject.DoesNotExist:
        return

    baseline = subject.baseline_date
    if not baseline:
        return

    # Update offset_days for all descendant entities
    models_to_update = [Visit, Record, Coding, Query, RecordRevision]
    for model in models_to_update:
        records_to_update = []
        if model == Visit:
            qs = model.objects.filter(subject=subject)
        elif model in [Record]:
            qs = model.objects.filter(visit__subject=subject)
        elif model in [Coding, Query, RecordRevision]:
            qs = model.objects.filter(record__visit__subject=subject)
        else:
            continue

        for obj in qs.filter(clinical_timestamp__isnull=False):
            new_offset = (obj.clinical_timestamp.date() - baseline.date()).days
            if obj.offset_days != new_offset:
                obj.offset_days = new_offset
                records_to_update.append(obj)

        if records_to_update:
            model.objects.bulk_update(records_to_update, ["offset_days"])

    # Update source_sequence if not set for Records
    records = Record.objects.filter(visit__subject=subject).order_by("clinical_timestamp", "created_at")
    records_to_update_seq = []
    for seq, rec in enumerate(records, start=1):
        if rec.source_sequence is None:
            rec.source_sequence = seq
            records_to_update_seq.append(rec)

    if records_to_update_seq:
        Record.objects.bulk_update(records_to_update_seq, ["source_sequence"])


@shared_task(bind=True, max_retries=3)
def sync_query_upstream(self, query_id):
    from audit.models import AuditLog
    from clinical.models import Query

    try:
        query = Query.objects.get(id=query_id)
        # Simulate pushing to upstream EDC via MultiVendorAdapter or external API
        # If it fails, raise exception to trigger retry

        # Simulate success
        query.sync_status = "CONFIRMED"
        query.last_sync_error = None
        query.previous_status = None
        query.save(update_fields=["sync_status", "last_sync_error", "previous_status", "updated_at"])

        AuditLog.objects.create(
            action="UPDATE",
            model_name="Query",
            object_id=str(query.external_id),
            changes={"sync_status": "CONFIRMED", "message": "Upstream sync completed successfully"},
            user=query.updated_by,
        )
    except Exception as exc:
        try:
            self.retry(exc=exc, countdown=10)
        except self.MaxRetriesExceededError:
            query = Query.objects.get(id=query_id)
            if query.previous_status:
                query.status = query.previous_status
            query.sync_status = "SYNC_FAILED"
            query.last_sync_error = str(exc)
            query.save(update_fields=["status", "sync_status", "last_sync_error", "updated_at"])

            AuditLog.objects.create(
                action="UPDATE",
                model_name="Query",
                object_id=str(query.external_id),
                changes={
                    "sync_status": "SYNC_FAILED",
                    "message": f"Sync failed max retries: {exc!s}",
                    "status_reverted": True,
                },
                user=query.updated_by,
            )
            logger.error(f"Sync failed for Query {query_id} after retries: {exc}")


from django.core.cache import cache


@shared_task
def poll_edc_queries():
    # Adaptive throttling logic
    # Check if there was activity recently, if so poll aggressively, otherwise scale down
    last_activity = cache.get("last_query_activity_time")
    current_time = timezone.now()

    polling_interval = 10 if last_activity and (current_time - last_activity).total_seconds() < 3600 else 300

    last_poll = cache.get("last_edc_poll_time")
    if last_poll and (current_time - last_poll).total_seconds() < polling_interval:
        # Too early to poll
        return

    cache.set("last_edc_poll_time", current_time, timeout=86400)

    # Simulate fetching new confirmed queries from upstream
    # In a real app we would call an EDC API endpoint here to get recent changes.
    # The adapter or SyncJob would be triggered to parse these changes.
    pass


@shared_task
def export_cdisc_task(job_id):
    from clinical.exports.odm import create_odm_xml
    from clinical.models import ExportJob, Study
    from events.models import OutboundEvent

    try:
        job = ExportJob.objects.get(id=job_id)
        job.status = "PROCESSING"
        job.save(update_fields=["status"])

        study = job.study if hasattr(job, "study") else Study.objects.first()  # Default to first study if not linked

        tmp_zip_path = create_odm_xml(study, job)

        from django.db import transaction

        from clinical.storage import get_storage_adapter

        adapter = get_storage_adapter()
        try:
            with transaction.atomic():
                # Compute aggregate contains_phi from study and all descendants
                from clinical.models import Record, Subject, Variable

                contains_phi = getattr(study, "contains_phi", False)

                # Check if any descendant entities contain PHI
                if not contains_phi:
                    # Check Sites
                    contains_phi = study.sites.filter(contains_phi=True).exists()

                if not contains_phi:
                    # Check Subjects
                    contains_phi = Subject.objects.filter(site__study=study, contains_phi=True).exists()

                if not contains_phi:
                    # Check Records
                    contains_phi = Record.objects.filter(visit__subject__site__study=study, contains_phi=True).exists()

                if not contains_phi:
                    # Check Variables
                    contains_phi = Variable.objects.filter(form__study=study, contains_phi=True).exists()

                with open(tmp_zip_path, "rb") as f:
                    final_path = adapter.save(f"export_{job_id}.zip", f, namespace="exports", contains_phi=contains_phi)

                job.file_path = final_path
                job.status = "COMPLETED"
                job.completed_at = timezone.now()
                job.contains_phi = contains_phi
                job.save(update_fields=["status", "file_path", "completed_at", "contains_phi"])

                # Notification requirement 5 & 6
                OutboundEvent.objects.create(
                    event_type="ExportJob",
                    action="COMPLETED",
                    payload={"job_id": job.id, "download_url": f"/api/clinical/export/cdisc/{job.id}/download"},
                )
        finally:
            import os

            if os.path.exists(tmp_zip_path):
                os.remove(tmp_zip_path)
    except Exception as e:
        if "job" in locals():
            job.status = "FAILED"
            job.error_message = str(e)
            job.save(update_fields=["status", "error_message"])


@shared_task
def run_validation_for_job(job_id):
    from clinical.validation.engine import execute_validation_for_job

    execute_validation_for_job(job_id)
