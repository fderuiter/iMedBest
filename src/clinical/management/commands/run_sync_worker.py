import logging
import time

from django.core.management.base import BaseCommand

from clinical.models import SyncJob, SyncTask

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Run the DB-backed sync queue worker'

    def handle(self, *args, **options):
        logger.info("Starting sync queue worker...")

        while True:
            try:
                jobs_to_process = SyncJob.objects.filter(status__in=['PENDING', 'PROCESSING']).order_by('created_at')

                processed_any = False
                for job in jobs_to_process:
                    if self.process_job(job):
                        processed_any = True

                if not processed_any:
                    time.sleep(2)

            except Exception as e:
                logger.error(f"Worker error: {e}")
                time.sleep(5)

    def process_job(self, job):
        if job.status == 'PENDING':
            job.status = 'PROCESSING'
            job.save(update_fields=['status'])

        active_tasks = job.tasks.exclude(status__in=['COMPLETED', 'FAILED'])
        if not active_tasks.exists():
            if job.tasks.filter(status='FAILED').exists():
                job.status = 'FAILED'
            else:
                job.status = 'COMPLETED'
            job.save(update_fields=['status'])
            return True

        min_level = active_tasks.order_by('hierarchy_level').first().hierarchy_level

        pending_tasks = list(active_tasks.filter(hierarchy_level=min_level, status='PENDING'))
        if not pending_tasks:
            return False

        entity_order = {
            'Study': 1, 'Site': 2,
            'Form': 1, 'Interval': 1, 'Subject': 2,
            'Variable': 1, 'Visit': 2,
            'Record': 1, 'Coding': 2, 'Query': 3, 'RecordRevision': 4
        }
        pending_tasks.sort(key=lambda t: entity_order.get(t.entity_type, 99))
        task = pending_tasks[0]

        updated = SyncTask.objects.filter(id=task.id, status='PENDING').update(status='PROCESSING')
        if not updated:
            return False

        task.refresh_from_db()

        try:
            self.execute_task(task)
            task.status = 'COMPLETED'
            task.save(update_fields=['status'])
        except Exception as e:
            logger.exception(f"Error processing task {task.id}: {e}")
            task.error_message = str(e)
            task.retry_count += 1
            if task.retry_count >= 3:
                task.status = 'FAILED'
            else:
                task.status = 'PENDING'
            task.save(update_fields=['status', 'error_message', 'retry_count'])

        return True

    def execute_task(self, task):
        from clinical.api import (
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

        class MockRequest:
            def __init__(self, user):
                self.user = user
                self.user_roles = ['cdisc']
                self.META = {}

        request = MockRequest(task.job.user)
        payload = task.payload
        entity_type = task.entity_type

        # Idempotency is guaranteed by update_or_create inside these sync_* functions
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
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")

