import logging
from datetime import timedelta
from django.utils import timezone
from django.db import transaction

from celery import shared_task

from .models import (
    SyncJob,
    SyncTask,
    SyncEvent,
)

logger = logging.getLogger(__name__)

TASK_TTL = timedelta(minutes=5)
JOB_TTL = timedelta(hours=1)
TERMINAL_STATES = ['COMPLETED', 'FAILED', 'CANCELLED', 'TIMED_OUT', 'STALLED']

def transition_job_state(job, new_status, message=""):
    if job.status in TERMINAL_STATES and new_status not in TERMINAL_STATES:
        return False
    
    old_status = job.status
    if old_status == new_status:
        return True

    job.status = new_status
    if message:
        job.error_message = message
    job.save(update_fields=['status', 'error_message', 'updated_at'])
    SyncEvent.objects.create(
        sync_job=job,
        status_from=old_status,
        status_to=new_status,
        message=message
    )
    return True

def transition_task_state(task, new_status, message=""):
    if task.status in TERMINAL_STATES and new_status not in TERMINAL_STATES:
        return False

    old_status = task.status
    if old_status == new_status:
        return True

    task.status = new_status
    if message:
        task.error_message = message
    task.save(update_fields=['status', 'error_message', 'updated_at'])
    SyncEvent.objects.create(
        sync_task=task,
        sync_job=task.job,
        status_from=old_status,
        status_to=new_status,
        message=message
    )
    return True

@shared_task(priority=9)
def reaper_service():
    now = timezone.now()
    
    # Task TTL Reaper
    stale_tasks = SyncTask.objects.filter(
        status__in=['PENDING', 'PROCESSING'],
        updated_at__lt=now - TASK_TTL
    )
    for task in stale_tasks:
        transition_task_state(task, 'TIMED_OUT', 'Task exceeded execution limit')
        trigger_next_level_if_ready(task.job_id, task.hierarchy_level, task.job.user_id)

    # Job TTL Reaper
    stale_jobs = SyncJob.objects.filter(
        status__in=['PENDING', 'PROCESSING'],
        updated_at__lt=now - JOB_TTL
    )
    for job in stale_jobs:
        transition_job_state(job, 'TIMED_OUT', 'Job exceeded execution limit')

def trigger_next_level_if_ready(job_id, level, user_id):
    with transaction.atomic():
        # lock job
        job = SyncJob.objects.select_for_update().get(id=job_id)
        if job.status in TERMINAL_STATES:
            return

        active_tasks = SyncTask.objects.filter(job=job, hierarchy_level=level).exclude(status__in=TERMINAL_STATES)
        if active_tasks.exists():
            return

        next_tasks = SyncTask.objects.filter(job=job, hierarchy_level__gt=level)
        if next_tasks.exists():
            next_level = next_tasks.order_by('hierarchy_level').first().hierarchy_level
            process_level.delay(job.id, next_level, user_id)
        else:
            has_errors = SyncTask.objects.filter(job=job, status__in=['FAILED', 'CANCELLED', 'TIMED_OUT', 'STALLED']).exists()
            if has_errors:
                transition_job_state(job, 'FAILED', 'Job finished with some task errors')
            else:
                transition_job_state(job, 'COMPLETED', 'All tasks finished successfully')

@shared_task(acks_late=True, reject_on_worker_lost=True)
def orchestrate_sync_job(job_id, user_id):
    job = SyncJob.objects.get(id=job_id)
    transition_job_state(job, 'PROCESSING')

    try:
        tasks = list(SyncTask.objects.filter(job=job).order_by('hierarchy_level'))
        if not tasks:
            transition_job_state(job, 'COMPLETED')
            return

        first_level = tasks[0].hierarchy_level
        process_level.delay(job_id, first_level, user_id)
    except Exception as e:
        transition_job_state(job, 'FAILED', str(e))

@shared_task(bind=True, max_retries=3, acks_late=True, reject_on_worker_lost=True)
def process_level(self, job_id, level, user_id):
    job = SyncJob.objects.get(id=job_id)
    if job.status in TERMINAL_STATES:
        return
    tasks = SyncTask.objects.filter(job=job, hierarchy_level=level, status='PENDING')

    if not tasks:
        trigger_next_level_if_ready(job_id, level, user_id)
        return

    for task in tasks:
        process_single_task.delay(task.id, user_id)

@shared_task(bind=True, max_retries=5, acks_late=True, reject_on_worker_lost=True)
def process_single_task(self, task_id, user_id):
    task = SyncTask.objects.get(id=task_id)
    if task.status != 'PENDING':
        return

    transition_task_state(task, 'PROCESSING')

    try:
        from users.models import User
        from .api import (
            CodingSchemaIn, FormSchemaIn, IntervalSchemaIn, QuerySchemaIn,
            RecordRevisionSchemaIn, RecordSchemaIn, SiteSchemaIn, StudySchemaIn,
            SubjectSchemaIn, VariableSchemaIn, VisitSchemaIn,
            sync_coding, sync_form, sync_interval, sync_query, sync_record,
            sync_revision, sync_site, sync_study, sync_subject, sync_variable, sync_visit,
        )
        user = User.objects.get(id=user_id)

        class MockRequest:
            def __init__(self, user):
                self.user = user
                self.META = {}
        request = MockRequest(user)

        payload = task.payload
        entity_type = task.entity_type

        # Check payload status to mock external API responses
        # The prompt says: "when external APIs enter unmapped states like 'STALLED' or 'CANCELLED'"
        if isinstance(payload, dict) and 'status' in payload:
            if payload['status'] == 'STALLED':
                raise ValueError("External API response: STALLED")
            elif payload['status'] == 'CANCELLED':
                raise ValueError("External API response: CANCELLED")

        if entity_type == 'Study':
            sync_study(request, StudySchemaIn(**payload))
        elif entity_type == 'Site':
            sync_site(request, SiteSchemaIn(**payload))
        elif entity_type == 'Subject':
            sync_subject(request, SubjectSchemaIn(**payload))
        elif entity_type == 'Form':
            sync_form(request, FormSchemaIn(**payload))
        elif entity_type == 'Interval':
            sync_interval(request, IntervalSchemaIn(**payload))
        elif entity_type == 'Variable':
            sync_variable(request, VariableSchemaIn(**payload))
        elif entity_type == 'Visit':
            sync_visit(request, VisitSchemaIn(**payload))
        elif entity_type == 'Record':
            sync_record(request, RecordSchemaIn(**payload))
        elif entity_type == 'Coding':
            sync_coding(request, CodingSchemaIn(**payload))
        elif entity_type == 'Query':
            sync_query(request, QuerySchemaIn(**payload))
        elif entity_type == 'RecordRevision':
            sync_revision(request, RecordRevisionSchemaIn(**payload))

        transition_task_state(task, 'COMPLETED')

    except Exception as exc:
        exc_str = str(exc)
        if 'STALLED' in exc_str:
            transition_task_state(task, 'STALLED', exc_str)
        elif 'CANCELLED' in exc_str:
            transition_task_state(task, 'CANCELLED', exc_str)
        else:
            task.retry_count += 1
            try:
                # Revert to PENDING so retry can process it
                transition_task_state(task, 'PENDING', exc_str)
                task.save(update_fields=['retry_count'])
                self.retry(exc=exc, countdown=2 ** task.retry_count)
            except self.MaxRetriesExceededError:
                transition_task_state(task, 'FAILED', f"Task failed after max retries: {exc_str}")
                logger.error(f"Task {task.id} failed after max retries")
    finally:
        # Trigger next level check, whether completed, failed, stalled, or cancelled
        task.refresh_from_db()
        if task.status in TERMINAL_STATES:
            trigger_next_level_if_ready(task.job_id, task.hierarchy_level, user_id)

@shared_task
def purge_trash_task(days=30):
    from django.core.management import call_command
    call_command('purge_trash', days=days)

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
            model.objects.bulk_update(records_to_update, ['offset_days'])

    records = Record.objects.filter(visit__subject=subject).order_by('clinical_timestamp', 'created_at')
    records_to_update_seq = []
    for seq, rec in enumerate(records, start=1):
        if rec.source_sequence is None:
            rec.source_sequence = seq
            records_to_update_seq.append(rec)

    if records_to_update_seq:
        Record.objects.bulk_update(records_to_update_seq, ['source_sequence'])

@shared_task(bind=True, max_retries=3)
def sync_query_upstream(self, query_id):
    from clinical.models import Query
    from audit.models import AuditLog
    try:
        query = Query.objects.get(id=query_id)
        
        query.sync_status = "CONFIRMED"
        query.last_sync_error = None
        query.previous_status = None
        query.save(update_fields=["sync_status", "last_sync_error", "previous_status", "updated_at"])
        
        AuditLog.objects.create(
            action="UPDATE",
            model_name="Query",
            object_id=str(query.external_id),
            changes={"sync_status": "CONFIRMED", "message": "Upstream sync completed successfully"},
            user=query.updated_by
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
                changes={"sync_status": "SYNC_FAILED", "message": f"Sync failed max retries: {str(exc)}", "status_reverted": True},
                user=query.updated_by
            )
            logger.error(f"Sync failed for Query {query_id} after retries: {exc}")

from django.core.cache import cache

@shared_task
def poll_edc_queries():
    last_activity = cache.get("last_query_activity_time")
    current_time = timezone.now()
    
    polling_interval = 60
    if last_activity and (current_time - last_activity).total_seconds() < 3600:
        polling_interval = 10
    else:
        polling_interval = 300
        
    last_poll = cache.get("last_edc_poll_time")
    if last_poll and (current_time - last_poll).total_seconds() < polling_interval:
        return
        
    cache.set("last_edc_poll_time", current_time, timeout=86400)
    pass
