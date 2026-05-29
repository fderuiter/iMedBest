import logging

from celery import chord, shared_task

from .models import SyncJob, SyncTask

logger = logging.getLogger(__name__)

@shared_task(acks_late=True, reject_on_worker_lost=True)
def orchestrate_sync_job(job_id, user_id):
    job = SyncJob.objects.get(id=job_id)
    job.status = 'PROCESSING'
    job.save(update_fields=['status'])

    levels = SyncTask.objects.filter(job=job).values_list('hierarchy_level', flat=True).distinct().order_by('hierarchy_level')

    if not levels:
        job.status = 'COMPLETED'
        job.save(update_fields=['status'])
        return

    process_dynamic_level.delay(job_id, list(levels), user_id)

@shared_task(acks_late=True, reject_on_worker_lost=True)
def process_dynamic_level(job_id, levels, user_id):
    if not levels:
        job = SyncJob.objects.get(id=job_id)
        if job.status != 'FAILED':
            job.status = 'COMPLETED'
            job.save(update_fields=['status'])
        return

    current_level = levels[0]
    remaining_levels = levels[1:]

    tasks = SyncTask.objects.filter(job_id=job_id, hierarchy_level=current_level, status='PENDING')
    task_signatures = [process_single_task.s(task.id, user_id) for task in tasks]

    if not task_signatures:
        process_dynamic_level.delay(job_id, remaining_levels, user_id)
    else:
        chord(task_signatures)(trigger_next_level.s(job_id, remaining_levels, user_id))

@shared_task(acks_late=True, reject_on_worker_lost=True)
def trigger_next_level(results, job_id, remaining_levels, user_id):
    job = SyncJob.objects.get(id=job_id)
    if job.status == 'FAILED':
        return
    process_dynamic_level.delay(job_id, remaining_levels, user_id)

@shared_task(bind=True, max_retries=5, acks_late=True, reject_on_worker_lost=True)
def process_single_task(self, task_id, user_id):
    task = SyncTask.objects.get(id=task_id)
    if task.status != 'PENDING':
        return

    task.status = 'PROCESSING'
    task.save(update_fields=['status'])

    try:
        from users.models import User

        from .registry import SyncRegistry

        user = User.objects.get(id=user_id)

        class MockRequest:
            def __init__(self, user):
                self.user = user
                self.user_roles = ['cdisc']
                self.META = {}
        request = MockRequest(user)

        payload = task.payload
        entity_type = task.entity_type

        registry_entry = SyncRegistry.get(entity_type)
        if not registry_entry:
            raise ValueError(f"Unknown entity type: {entity_type}")

        sync_func = registry_entry['sync_func']
        schema_cls = registry_entry['schema_in']

        sync_func(request, schema_cls(**payload))

        task.status = 'COMPLETED'
        task.save(update_fields=['status'])

    except Exception as exc:
        task.error_message = str(exc)
        task.retry_count += 1
        try:
            task.status = 'PENDING'
            task.save(update_fields=['status', 'error_message', 'retry_count'])
            self.retry(exc=exc, countdown=2 ** task.retry_count)
        except self.MaxRetriesExceededError:
            task.status = 'FAILED'
            task.save(update_fields=['status'])
            logger.error(f"Task {task.id} failed after max retries")
