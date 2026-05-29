import logging
from django.core.management.base import BaseCommand
from clinical.models import SyncJob
from clinical.tasks import orchestrate_sync_job

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Run the Celery orchestrator natively (no polling)'

    def handle(self, *args, **options):
        # We process pending jobs through celery natively instead of polling loop
        jobs_to_process = SyncJob.objects.filter(status='PENDING').order_by('created_at')
        for job in jobs_to_process:
            self.process_job(job)

    def process_job(self, job):
        # Trigger the celery workflow natively
        orchestrate_sync_job(job.id, job.user.id)
        return True
