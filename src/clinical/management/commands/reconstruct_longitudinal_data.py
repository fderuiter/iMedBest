from django.core.management.base import BaseCommand
from clinical.models import Coding, Query, Record, RecordRevision, Subject, Visit, Form, Interval, Site, Study, Variable
from clinical.graph import ClinicalGraphEngine
from audit.signals import safe_model_to_dict

class Command(BaseCommand):
    help = "Reconstruct longitudinal data for legacy records and recalculate offsets based on updated baseline."

    def handle(self, *args, **options):
        self.stdout.write("Backfilling missing clinical_timestamps with created_at...")
        engine = ClinicalGraphEngine()
        
        models_to_backfill = [Study, Site, Subject, Form, Interval, Variable, Visit, Record, Coding, Query, RecordRevision]
        for model in models_to_backfill:
            records_to_update = []
            old_data_map = {}
            for obj in model.objects.filter(clinical_timestamp__isnull=True):
                old_data_map[obj.id] = safe_model_to_dict(obj)
                obj.clinical_timestamp = obj.created_at
                records_to_update.append(obj)
            if records_to_update:
                engine.bulk_update_with_audit(model, records_to_update, ["clinical_timestamp"], old_data_map)

        self.stdout.write("Recalculating offsets and sequences via Graph Engine...")
        subjects = Subject.objects.all()
        for subject in subjects:
            engine.reconstruct_timeline(subject)

        self.stdout.write("Done.")
