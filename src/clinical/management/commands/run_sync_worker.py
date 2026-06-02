import logging
import time

from django.core.management.base import BaseCommand

from clinical.models import SyncJob, SyncTask

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run the DB-backed sync queue worker"

    def handle(self, *args, **options):
        logger.info("Starting sync queue worker...")

        # Reset any interrupted tasks back to PENDING so they can be resumed
        SyncTask.objects.filter(status="PROCESSING").update(status="PENDING")

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
            job.save(update_fields=["status", "updated_at"])

        active_tasks = job.tasks.exclude(status__in=["COMPLETED", "FAILED"])
        if not active_tasks.exists():
            if job.tasks.filter(status="FAILED").exists():
                job.status = "FAILED"
            else:
                job.status = "COMPLETED"
            job.save(update_fields=["status", "updated_at"])
            return True

        min_level = active_tasks.order_by("hierarchy_level").first().hierarchy_level

        pending_tasks = list(active_tasks.filter(hierarchy_level=min_level, status="PENDING"))
        if not pending_tasks:
            return False

        entity_order = {
            "Study": 1,
            "Site": 2,
            "Form": 1,
            "Interval": 1,
            "Subject": 2,
            "Variable": 1,
            "Visit": 2,
            "Record": 1,
            "Coding": 2,
            "Query": 3,
            "RecordRevision": 4,
        }
        pending_tasks.sort(key=lambda t: entity_order.get(t.entity_type, 99))
        task = pending_tasks[0]

        updated = SyncTask.objects.filter(id=task.id, status="PENDING").update(status="PROCESSING")
        if not updated:
            return False

        task.refresh_from_db()

        try:
            self.execute_task(task)
            task.status = "COMPLETED"
            task.save(update_fields=["status", "updated_at"])
        except Exception as e:
            logger.exception(f"Error processing task {task.id}: {e}")
            task.error_message = str(e)
            task.retry_count += 1
            if task.retry_count >= 3:
                task.status = "FAILED"
            else:
                task.status = "PENDING"
            task.save(update_fields=["status", "error_message", "retry_count", "updated_at"])

        return True

    def execute_task(self, task):
        from django.db import transaction

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
        with transaction.atomic():
            adapter.sync_entity(request, entity_type, payload)
