import logging
import time

from django.core.management.base import BaseCommand

from clinical.models import SyncJob, SyncTask

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run the DB-backed sync queue worker"

    def handle(self, *args, **options):
        logger.info("Starting sync queue worker...")

        while True:
            try:
                jobs_to_process = SyncJob.objects.filter(status__in=["PENDING", "PROCESSING"]).order_by("created_at")

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
        if job.status == "PENDING":
            job.status = "PROCESSING"
            job.save(update_fields=["status"])

        active_tasks = job.tasks.exclude(status__in=["COMPLETED", "FAILED"])
        if not active_tasks.exists():
            if job.tasks.filter(status="FAILED").exists():
                job.status = "FAILED"
            else:
                job.status = "COMPLETED"
            job.save(update_fields=["status"])
            return True

        pending_tasks = active_tasks.filter(status="PENDING")
        if not pending_tasks.exists():
            return False

        # Find a task whose dependencies are all COMPLETED
        task_to_run = None
        for task in pending_tasks:
            deps = task.dependencies.all()
            if all(d.status == "COMPLETED" for d in deps):
                task_to_run = task
                break
                
        if not task_to_run:
            # Check for failed dependencies
            failed_found = False
            for task in pending_tasks:
                deps = task.dependencies.all()
                if any(d.status == "FAILED" for d in deps):
                    task.status = "FAILED"
                    task.error_message = "Dependency failed"
                    task.save(update_fields=["status", "error_message"])
                    failed_found = True
            
            if failed_found:
                return True
            return False

        task = task_to_run
        updated = SyncTask.objects.filter(id=task.id, status="PENDING").update(status="PROCESSING")
        if not updated:
            return False

        task.refresh_from_db()

        try:
            self.execute_task(task)
            task.status = "COMPLETED"
            task.save(update_fields=["status"])
        except Exception as e:
            logger.exception(f"Error processing task {task.id}: {e}")
            task.error_message = str(e)
            task.retry_count += 1
            if task.retry_count >= 3:
                task.status = "FAILED"
            else:
                task.status = "PENDING"
            task.save(update_fields=["status", "error_message", "retry_count"])

        return True

    def execute_task(self, task):
        """
        Execute a sync task through the vendor adapter and mark the returned entity as validated when applicable.
        
        This constructs a minimal request object for the task's job/user/provider, invokes the provider-specific MultiVendorAdapter to synchronize the task's entity payload, and, if the adapter returns a single model-like object (truthy and not a tuple), sets its `is_validated` flag to True and persists that change (updating `is_validated` and `updated_at`).
        
        Parameters:
            task: The SyncTask instance to execute (provides access to job, provider, payload, and entity_type).
        """
        from clinical.adapter import MultiVendorAdapter

        class MockRequest:
            def __init__(self, user, provider):
                self.user = user
                self.user_roles = ["cdisc"]
                self.provider = provider
                self.META = {}

        request = MockRequest(task.job.user, task.job.provider)
        payload = task.payload
        entity_type = task.entity_type

        adapter = MultiVendorAdapter(task.job.provider)
        result = adapter.sync_entity(request, entity_type, payload)
        
        if result and not isinstance(result, tuple):
            result.is_validated = True
            result.save(update_fields=["is_validated", "updated_at"])
