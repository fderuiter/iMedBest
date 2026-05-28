import logging

from celery import shared_task
from django.db import transaction

from .models import (
    Form,
    Record,
    SyncJob,
    SyncTask,
    Variable,
    Visit,
)

logger = logging.getLogger(__name__)

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
        try:
            prune_log = run_pruning(job)
            if prune_log:
                summary = "Pruning Summary:\n" + "\n".join(prune_log)
                if job.error_message:
                    job.error_message += "\n\n" + summary
                else:
                    job.error_message = summary
                job.save(update_fields=['error_message'])
        except Exception as e:
            logger.error(f"Pruning failed for job {job.id}: {e}")

        job.status = 'COMPLETED'
        job.save(update_fields=['status'])




def get_sync_scopes(job):
    scopes = {
        'Form': set(),
        'Variable': set(),
        'Visit': set(),
    }

    synced_entities = {
        'Study': set(),
        'Site': set(),
        'Subject': set(),
        'Form': set(),
        'Interval': set(),
        'Variable': set(),
        'Visit': set(),
    }

    for task in SyncTask.objects.filter(job=job):
        etype = task.entity_type
        payload = task.payload
        ext_id = payload.get('external_id')
        if ext_id:
            if etype in synced_entities:
                synced_entities[etype].add(ext_id)

            if etype == 'Study':
                scopes['Form'].add(ext_id)
            elif etype == 'Form':
                scopes['Variable'].add(ext_id)
                if 'study_ext_id' in payload:
                    scopes['Form'].add(payload['study_ext_id'])
            elif etype == 'Subject':
                scopes['Visit'].add(ext_id)
            elif etype == 'Variable' and 'form_ext_id' in payload:
                scopes['Variable'].add(payload['form_ext_id'])
            elif etype == 'Visit' and 'subject_ext_id' in payload:
                scopes['Visit'].add(payload['subject_ext_id'])

    return scopes, synced_entities

def has_clinical_dependencies(entity_type, entity):
    if entity_type == 'Variable':
        return Record.objects.filter(variable=entity).exists()
    if entity_type == 'Visit':
        return Record.objects.filter(visit=entity).exists()
    if entity_type == 'Form':
        return Record.objects.filter(variable__form=entity).exists()
    return False

@transaction.atomic
def run_pruning(job):
    scopes, synced_entities = get_sync_scopes(job)
    prune_log = []

    variables_to_prune = Variable.objects.filter(
        form__external_id__in=scopes['Variable']
    ).exclude(external_id__in=synced_entities['Variable'])

    for var in variables_to_prune:
        if has_clinical_dependencies('Variable', var):
            prune_log.append(f"PRESERVED Variable {var.external_id}: Has clinical dependencies")
        else:
            prune_log.append(f"DELETED Variable {var.external_id}")
            var.delete()

    visits_to_prune = Visit.objects.filter(
        subject__external_id__in=scopes['Visit']
    ).exclude(external_id__in=synced_entities['Visit'])

    for visit in visits_to_prune:
        if has_clinical_dependencies('Visit', visit):
            prune_log.append(f"PRESERVED Visit {visit.external_id}: Has clinical dependencies")
        else:
            prune_log.append(f"DELETED Visit {visit.external_id}")
            visit.delete()

    forms_to_prune = Form.objects.filter(
        study__external_id__in=scopes['Form']
    ).exclude(external_id__in=synced_entities['Form'])

    for form in forms_to_prune:
        if has_clinical_dependencies('Form', form):
            prune_log.append(f"PRESERVED Form {form.external_id}: Has clinical dependencies")
        else:
            prune_log.append(f"DELETED Form {form.external_id}")
            form.delete()

    return prune_log

