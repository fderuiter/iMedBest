import time
import traceback

from django.core.management.base import BaseCommand
from django.db import transaction

from clinical.models import Coding, Form, Interval, Query, Record, RecordRevision, Site, Study, Subject, Variable, Visit
from jobs.models import Job, JobStatus


class Command(BaseCommand):
    help = "Run background jobs"

    def handle(self, *args, **options):
        self.stdout.write("Starting background worker...")
        while True:
            job = self.get_next_job()
            if not job:
                time.sleep(1)
                continue

            self.stdout.write(f"Processing job {job.id} ({job.job_type})")
            try:
                with transaction.atomic():
                    self.process_job(job)
                job.status = JobStatus.COMPLETED
                job.save(update_fields=["status", "result", "updated_at"])
                self.stdout.write(f"Completed job {job.id}")
            except Exception as e:
                job.status = JobStatus.FAILED
                job.error_log = traceback.format_exc()
                job.save(update_fields=["status", "error_log", "updated_at"])
                self.stdout.write(f"Failed job {job.id}: {e}")

    def get_next_job(self):
        with transaction.atomic():
            job = Job.objects.select_for_update(skip_locked=True).filter(
                status=JobStatus.QUEUED
            ).order_by("created_at").first()
            if job:
                job.status = JobStatus.PROCESSING
                job.save(update_fields=["status", "updated_at"])
                return job
        return None

    def process_job(self, job):
        # We handle single item or list of items in the payload
        payloads = job.payload if isinstance(job.payload, list) else [job.payload]
        results = []

        for item in payloads:
            if job.job_type == "sync_study":
                study, _ = Study.objects.update_or_create(external_id=item["external_id"], defaults={"name": item.get("name")})
                results.append(str(study.id))
            elif job.job_type == "sync_site":
                study = Study.objects.get(external_id=item["study_ext_id"])
                site, _ = Site.objects.update_or_create(external_id=item["external_id"], defaults={"study": study, "name": item.get("name")})
                results.append(str(site.id))
            elif job.job_type == "sync_subject":
                site = Site.objects.get(external_id=item["site_ext_id"])
                subject, _ = Subject.objects.update_or_create(external_id=item["external_id"], defaults={"site": site, "name": item.get("name")})
                results.append(str(subject.id))
            elif job.job_type == "sync_form":
                study = Study.objects.get(external_id=item["study_ext_id"])
                form, _ = Form.objects.update_or_create(external_id=item["external_id"], defaults={"study": study, "name": item.get("name")})
                results.append(str(form.id))
            elif job.job_type == "sync_interval":
                study = Study.objects.get(external_id=item["study_ext_id"])
                interval, _ = Interval.objects.update_or_create(external_id=item["external_id"], defaults={"study": study, "name": item.get("name")})
                results.append(str(interval.id))
            elif job.job_type == "sync_variable":
                form = Form.objects.get(external_id=item["form_ext_id"])
                variable, _ = Variable.objects.update_or_create(external_id=item["external_id"], defaults={"form": form, "name": item.get("name")})
                results.append(str(variable.id))
            elif job.job_type == "sync_visit":
                subject = Subject.objects.get(external_id=item["subject_ext_id"])
                interval = Interval.objects.get(external_id=item["interval_ext_id"])
                visit, _ = Visit.objects.update_or_create(external_id=item["external_id"], defaults={"subject": subject, "interval": interval})
                results.append(str(visit.id))
            elif job.job_type == "sync_record":
                visit = Visit.objects.get(external_id=item["visit_ext_id"])
                variable = Variable.objects.get(external_id=item["variable_ext_id"])
                record, _ = Record.objects.update_or_create(external_id=item["external_id"], defaults={"visit": visit, "variable": variable, "value": item.get("value")})
                results.append(str(record.id))
            elif job.job_type == "sync_coding":
                record = Record.objects.get(external_id=item["record_ext_id"])
                coding, _ = Coding.objects.update_or_create(external_id=item["external_id"], defaults={"record": record, "code": item.get("code")})
                results.append(str(coding.id))
            elif job.job_type == "sync_query":
                record = Record.objects.get(external_id=item["record_ext_id"])
                query, _ = Query.objects.update_or_create(external_id=item["external_id"], defaults={"record": record, "text": item.get("text")})
                results.append(str(query.id))
            elif job.job_type == "sync_revision":
                record = Record.objects.get(external_id=item["record_ext_id"])
                revision, _ = RecordRevision.objects.update_or_create(external_id=item["external_id"], defaults={"record": record, "value": item.get("value")})
                results.append(str(revision.id))
            else:
                raise ValueError(f"Unknown job type: {job.job_type}")

        job.result = results
