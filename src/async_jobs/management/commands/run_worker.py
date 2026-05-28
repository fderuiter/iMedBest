import time
import traceback

from django.core.management.base import BaseCommand
from django.db import transaction

from async_jobs.models import Job, Metric
from clinical import services
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
)


class Command(BaseCommand):
    help = 'Run the background job worker'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting background worker..."))

        endpoints = {
            "sync_study": services.sync_study,
            "sync_site": services.sync_site,
            "sync_subject": services.sync_subject,
            "sync_form": services.sync_form,
            "sync_interval": services.sync_interval,
            "sync_variable": services.sync_variable,
            "sync_visit": services.sync_visit,
            "sync_record": services.sync_record,
            "sync_coding": services.sync_coding,
            "sync_query": services.sync_query,
            "sync_revision": services.sync_revision,
        }

        schemas = {
            "sync_study": StudySchemaIn,
            "sync_site": SiteSchemaIn,
            "sync_subject": SubjectSchemaIn,
            "sync_form": FormSchemaIn,
            "sync_interval": IntervalSchemaIn,
            "sync_variable": VariableSchemaIn,
            "sync_visit": VisitSchemaIn,
            "sync_record": RecordSchemaIn,
            "sync_coding": CodingSchemaIn,
            "sync_query": QuerySchemaIn,
            "sync_revision": RecordRevisionSchemaIn,
        }

        while True:
            # Report queue depth metric
            queue_depth = Job.objects.filter(status='Pending').count()
            Metric.objects.create(name='queue_depth', value=queue_depth)

            # Get the oldest pending job
            job = None
            with transaction.atomic():
                job = (
                    Job.objects.select_for_update(skip_locked=True)
                    .filter(status='Pending')
                    .order_by('created_at')
                    .first()
                )
                if job:
                    job.status = 'Processing'
                    job.save(update_fields=['status'])

            if not job:
                time.sleep(1)
                continue

            start_time = time.time()
            success = False

            try:
                # Process job
                handler = endpoints[job.endpoint]
                schema_cls = schemas[job.endpoint]
                payload_obj = schema_cls(**job.payload)

                # Execute handler
                result_obj = handler(payload_obj)

                job.result = {
                    "id": str(getattr(result_obj, "id", "")),
                    "external_id": str(getattr(result_obj, "external_id", ""))
                }
                job.status = 'Completed'
                job.error = None
                success = True
            except Exception:
                job.error = traceback.format_exc()
                job.retries += 1
                if job.retries >= 3:
                    job.status = 'Failed'
                else:
                    job.status = 'Pending'
            finally:
                job.save()

            # Report processing latency metric
            latency_ms = (time.time() - start_time) * 1000
            Metric.objects.create(name='task_latency_ms', value=latency_ms)

            # Report throughput (success/failure)
            Metric.objects.create(name='task_success', value=1 if success else 0)
