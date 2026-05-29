from django.core.management.base import BaseCommand

from clinical.models import Coding, Query, Record, RecordRevision, Subject, Visit


class Command(BaseCommand):
    help = "Reconstruct longitudinal data for legacy records and recalculate offsets based on updated baseline."

    def handle(self, *args, **options):
        # The backfilling should estimate clinical_timestamp from created_at if missing
        self.stdout.write("Backfilling missing clinical_timestamps with created_at...")
        from clinical.models import Form, Interval, Site, Study, Variable
        for model in [Study, Site, Subject, Form, Interval, Variable, Visit, Record, Coding, Query, RecordRevision]:
            records_to_update = []
            for obj in model.objects.filter(clinical_timestamp__isnull=True):
                obj.clinical_timestamp = obj.created_at
                records_to_update.append(obj)
            if records_to_update:
                model.objects.bulk_update(records_to_update, ['clinical_timestamp'])

        self.stdout.write("Recalculating offsets...")
        # Since offset_days depends on the subject's baseline, and a subject's baseline depends on Visit,
        # we can just loop through all entities that have a subject and call save() to recalculate.
        # However, save() might be slow for bulk. Let's use bulk update if possible.

        subjects = Subject.objects.all()
        baseline_cache = {}
        for subject in subjects:
            baseline_cache[subject.id] = subject.baseline_date

        for model in [Visit, Record, Coding, Query, RecordRevision]:
            records_to_update = []
            for obj in model.objects.all():
                try:
                    subject = obj.get_subject()
                    if subject and obj.clinical_timestamp:
                        baseline = baseline_cache.get(subject.id)
                        if baseline:
                            obj.offset_days = (obj.clinical_timestamp.date() - baseline.date()).days
                            records_to_update.append(obj)
                except Exception:
                    pass
            if records_to_update:
                model.objects.bulk_update(records_to_update, ['offset_days'])

        # Update sequences (e.g. source_sequence) if not set.
        # We can just leave them if they are not set, or backfill them sequentially.
        # For VS (Record), order by clinical_timestamp then set source_sequence
        for subject in subjects:
            records = Record.objects.filter(visit__subject=subject).order_by('clinical_timestamp', 'created_at')
            records_to_update_seq = []
            for seq, rec in enumerate(records, start=1):
                if rec.source_sequence is None:
                    rec.source_sequence = seq
                    records_to_update_seq.append(rec)
            if records_to_update_seq:
                Record.objects.bulk_update(records_to_update_seq, ['source_sequence'])

        self.stdout.write("Done.")
