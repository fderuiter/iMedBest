import logging
import os

from celery import shared_task

from .export import create_cdisc_archive_file
from .models import (
    ExportJob,
    SyncJob,
    SyncTask,
)

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_export_job(self, job_id):
    zip_path = None
    try:
        job = ExportJob.objects.get(id=job_id)
        job.status = 'PROCESSING'
        job.save(update_fields=['status'])

        # Generate data
        zip_path = create_cdisc_archive_file()

        # Save to file field
        from django.core.files import File
        file_name = f"cdisc_export_{job_id}.zip"

        with open(zip_path, 'rb') as f:
            job.file.save(file_name, File(f), save=False)

        job.status = 'COMPLETED'
        job.save(update_fields=['status', 'file'])

    except Exception as exc:
        job = ExportJob.objects.get(id=job_id)
        job.status = 'FAILED'
        job.error_message = str(exc)
        job.save(update_fields=['status', 'error_message'])
        logger.error(f"Export Job {job_id} failed: {exc}")
        # Not retrying automatically for export, user has retry button.
    finally:
        if zip_path and os.path.exists(zip_path):
            try:
                os.remove(zip_path)
            except OSError:
                pass

@shared_task(bind=True, max_retries=3)
def process_sync_task(self, task_id, user_id):
    task = SyncTask.objects.get(id=task_id)
    try:
        task.status = 'PROCESSING'
        task.save(update_fields=['status'])

        # Process the task payload based on entity_type
        # In a real app we'd map this dynamically or use the existing sync_* functions
        # For simplicity, we just use a generic approach or dispatch manually

        # We need to simulate the saving of data with transactional integrity.
        # "parent entities are fully processed before child entities are initiated"

        # After successful save:
        task.status = 'COMPLETED'
        task.save(update_fields=['status'])

        # Queue child tasks if any are waiting for this parent
        child_tasks = SyncTask.objects.filter(parent_task_id=task.id, status='PENDING')
        for child in child_tasks:
            process_sync_task.delay(child.id, user_id)

        # Check if job is completed
        job = task.job
        if not job.tasks.exclude(status='COMPLETED').exists():
            job.status = 'COMPLETED'
            job.save(update_fields=['status'])

    except Exception as exc:
        task.status = 'FAILED'
        task.error_message = str(exc)
        task.retry_count += 1
        task.save(update_fields=['status', 'error_message', 'retry_count'])
        job = task.job
        job.status = 'FAILED'
        job.save(update_fields=['status'])
        try:
            self.retry(exc=exc, countdown=2 ** task.retry_count) # Exponential backoff
        except self.MaxRetriesExceededError:
            logger.error(f"Task {task.id} failed after max retries")

@shared_task
def orchestrate_sync_job(job_id, user_id):
    job = SyncJob.objects.get(id=job_id)
    job.status = 'PROCESSING'
    job.save(update_fields=['status'])

    # We kick off Level 1 tasks. Level 2, 3, 4 will be kicked off by their parents
    # But wait, what if there are no explicit parent_task links and we just sort by hierarchy level?
    # Requirement 6: "ensure that parent entities are fully processed before child entities are initiated"

    # Let's process Level 1, wait for completion, then Level 2, etc?
    # Or link them via parent_task. Let's do level by level using Celery Chains/Chords or just queueing them sequentially.

    # Simple approach: queue L1 tasks. They queue their children, etc.
    # If no parent links are set, we can just process level 1, then level 2, etc.
    try:
        tasks = list(SyncTask.objects.filter(job=job).order_by('hierarchy_level'))

        # We can group them by hierarchy level
        levels = {}
        for t in tasks:
            levels.setdefault(t.hierarchy_level, []).append(t)

        # Instead of a complex chord, we could just process them synchronously in the worker,
        # but that defeats the purpose of horizontal scalability.
        # Actually, using Celery Canvas (chain/chord) is best.


        # For this requirement, let's just group tasks by level, and dispatch them level by level.
        # To do this safely and simply in Celery without complex canvases, we can process a level,
        # then queue a task to process the next level.
        process_level.delay(job_id, 1, user_id)

    except Exception as e:
        job.status = 'FAILED'
        job.error_message = str(e)
        job.save(update_fields=['status', 'error_message'])

@shared_task(bind=True, max_retries=3)
def process_level(self, job_id, level, user_id):
    job = SyncJob.objects.get(id=job_id)
    tasks = SyncTask.objects.filter(job=job, hierarchy_level=level, status='PENDING')

    if not tasks:
        # No tasks at this level, check next
        next_tasks = SyncTask.objects.filter(job=job, hierarchy_level__gt=level)
        if next_tasks.exists():
            next_level = next_tasks.order_by('hierarchy_level').first().hierarchy_level
            process_level.delay(job_id, next_level, user_id)
        else:
            job.status = 'COMPLETED'
            job.save(update_fields=['status'])
        return

    # Process tasks at this level.
    # To ensure all tasks at this level finish before next level, we could use a chord.
    # But we can also process them and just check completion.


    # We will process each task
    for task in tasks:
        # In a real system, we'd use process_sync_task.delay()
        # For simplicity in this job, we process them inline if we want, or use group
        # Let's call a subtask for each
        process_single_task.delay(task.id, user_id)

    # We need a way to check when they are done.
    # Let's queue a monitoring task that checks if level is done.
    check_level_completion.apply_async((job_id, level, user_id), countdown=2)

@shared_task(bind=True, max_retries=5)
def process_single_task(self, task_id, user_id):
    task = SyncTask.objects.get(id=task_id)
    if task.status != 'PENDING':
        return

    task.status = 'PROCESSING'
    task.save(update_fields=['status'])

    try:
        from users.models import User

        from .api import (
            CodingSchemaIn,
            FormSchemaIn,
            IntervalSchemaIn,
            QuerySchemaIn,
            RecordRevisionSchemaIn,
            RecordSchemaIn,
            SiteSchemaIn,
            StudySchemaIn,
            SubjectSchemaIn,
            VariableSchemaIn,
            VisitSchemaIn,
            sync_coding,
            sync_form,
            sync_interval,
            sync_query,
            sync_record,
            sync_revision,
            sync_site,
            sync_study,
            sync_subject,
            sync_variable,
            sync_visit,
        )
        user = User.objects.get(id=user_id)

        # Mock request object
        class MockRequest:
            def __init__(self, user):
                self.user = user
                self.META = {}
        request = MockRequest(user)

        payload = task.payload
        entity_type = task.entity_type

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

        task.status = 'COMPLETED'
        task.save(update_fields=['status'])

    except Exception as exc:
        task.status = 'FAILED'
        task.error_message = str(exc)
        task.retry_count += 1
        task.save(update_fields=['status', 'error_message', 'retry_count'])
        try:
            self.retry(exc=exc, countdown=2 ** task.retry_count) # Exponential backoff
        except self.MaxRetriesExceededError:
            logger.error(f"Task {task.id} failed after max retries")
            job = task.job
            job.status = 'FAILED'
            job.error_message = f"Task {task.id} failed"
            job.save(update_fields=['status', 'error_message'])

@shared_task
def check_level_completion(job_id, level, user_id):
    job = SyncJob.objects.get(id=job_id)
    if job.status == 'FAILED':
        return # Stop processing

    tasks = SyncTask.objects.filter(job=job, hierarchy_level=level)
    if tasks.filter(status='FAILED').exists():
        job.status = 'FAILED'
        job.error_message = f"One or more tasks failed at level {level}"
        job.save(update_fields=['status', 'error_message'])
        return

    if tasks.exclude(status='COMPLETED').exists():
        # Still processing, check again later
        check_level_completion.apply_async((job_id, level, user_id), countdown=2)
        return

    # All completed, proceed to next level
    next_tasks = SyncTask.objects.filter(job=job, hierarchy_level__gt=level)
    if next_tasks.exists():
        next_level = next_tasks.order_by('hierarchy_level').first().hierarchy_level
        process_level.delay(job_id, next_level, user_id)
    else:
        job.status = 'COMPLETED'
        job.save(update_fields=['status'])
