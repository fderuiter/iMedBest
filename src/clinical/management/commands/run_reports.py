from django.utils import timezone
from datetime import timedelta
import time
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from clinical.models import ReportJob
from clinical.export import _generate_cdisc_export_file

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Run pending report/export jobs using the database as a queue"

    def handle(self, *args, **options):
        self.stdout.write("Starting report job runner...")
        last_cleanup = time.time()
        while True:
            try:
                self.process_next_job()
                
                # Cleanup jobs older than 7 days every hour
                if time.time() - last_cleanup > 3600:
                    self.cleanup_old_jobs()
                    last_cleanup = time.time()
            except Exception as e:
                logger.error(f"Error processing job: {e}")
            time.sleep(2)  # poll every 2 seconds

    def cleanup_old_jobs(self):
        cutoff = timezone.now() - timedelta(days=7)
        old_jobs = ReportJob.objects.filter(created_at__lt=cutoff)
        count = old_jobs.count()
        if count > 0:
            for job in old_jobs:
                if job.file:
                    job.file.delete(save=False)
            old_jobs.delete()
            self.stdout.write(f"Cleaned up {count} jobs older than 7 days")

    def process_next_job(self):
        # We need to find the next PENDING job and lock it
        with transaction.atomic():
            # select_for_update(skip_locked=True) ensures that multiple workers don't pick the same job
            job = ReportJob.objects.select_for_update(skip_locked=True).filter(status='PENDING').first()
            if not job:
                return

            # Mark as processing
            job.status = 'PROCESSING'
            job.save(update_fields=['status'])

        # Now process the job outside the lock so we don't hold the lock for a long time
        self.stdout.write(f"Processing job {job.id} of type {job.report_type}")
        
        try:
            if job.report_type == 'cdisc_export':
                # Call a function that generates the file and saves it
                _generate_cdisc_export_file(job)
            else:
                raise ValueError(f"Unknown report_type: {job.report_type}")
            
            job.status = 'COMPLETED'
            job.progress = 100
            job.save(update_fields=['status', 'progress', 'file'])
            self.stdout.write(f"Completed job {job.id}")

        except Exception as e:
            logger.exception(f"Job {job.id} failed")
            job.status = 'FAILED'
            job.error_message = str(e)
            job.save(update_fields=['status', 'error_message'])

