import logging
from django.db import transaction
from audit.tasks import create_audit_log_task
from audit.signals import safe_model_to_dict

logger = logging.getLogger(__name__)

def get_provider_dependencies(provider):
    default_mapping = {
        "Study": [],
        "Site": ["Study"],
        "Subject": ["Site"],
        "Form": ["Study"],
        "Interval": ["Study"],
        "Variable": ["Form"],
        "Visit": ["Subject", "Interval"],
        "Record": ["Visit", "Variable"],
        "Coding": ["Record"],
        "Query": ["Record"],
        "RecordRevision": ["Record"],
    }
    if provider and provider.hierarchy_mapping:
        return provider.hierarchy_mapping
    return default_mapping

def topological_sort_entities(entities, provider):
    dependencies = get_provider_dependencies(provider)
    
    depths = {}
    
    def get_depth(etype, visited):
        if etype in depths:
            return depths[etype]
        if etype in visited:
            return 0  # Cycle handling
        visited.add(etype)
        deps = dependencies.get(etype, [])
        if not deps:
            depth = 1
        else:
            depth = 1 + max([get_depth(d, visited) for d in deps] + [0])
        depths[etype] = depth
        visited.remove(etype)
        return depth
        
    for etype in dependencies.keys():
        get_depth(etype, set())
        
    for e in entities:
        if e.entity_type not in depths:
            get_depth(e.entity_type, set())
            
    return sorted(entities, key=lambda e: depths.get(e.entity_type, 99))

class ClinicalGraphEngine:
    def reconstruct_timeline(self, subject):
        from clinical.models import Visit, Record, Coding, Query, RecordRevision
        
        baseline = subject.baseline_date
        if not baseline:
            return

        models_to_update = [Visit, Record, Coding, Query, RecordRevision]
        for model in models_to_update:
            records_to_update = []
            old_data_map = {}
            if model == Visit:
                qs = model.objects.filter(subject=subject)
            elif model == Record:
                qs = model.objects.filter(visit__subject=subject)
            elif model in [Coding, Query, RecordRevision]:
                qs = model.objects.filter(record__visit__subject=subject)
            else:
                continue

            for obj in qs.filter(clinical_timestamp__isnull=False):
                new_offset = (obj.clinical_timestamp.date() - baseline.date()).days
                if obj.offset_days != new_offset:
                    old_data_map[obj.id] = safe_model_to_dict(obj)
                    obj.offset_days = new_offset
                    records_to_update.append(obj)

            if records_to_update:
                self.bulk_update_with_audit(model, records_to_update, ["offset_days"], old_data_map)

        # Update sequences if not set or just re-calculate sequentially
        records = Record.objects.filter(visit__subject=subject).order_by("clinical_timestamp", "created_at")
        records_to_update_seq = []
        old_data_map = {}
        for seq, rec in enumerate(records, start=1):
            if rec.source_sequence != seq:
                old_data_map[rec.id] = safe_model_to_dict(rec)
                rec.source_sequence = seq
                records_to_update_seq.append(rec)

        if records_to_update_seq:
            self.bulk_update_with_audit(Record, records_to_update_seq, ["source_sequence"], old_data_map)

    def bulk_update_with_audit(self, model, instances, fields, old_data_map=None, user=None):
        if not instances:
            return
        
        if old_data_map is None:
            old_data_map = {}

        # Save to database
        model.objects.bulk_update(instances, fields)

        # Generate Audit Logs
        for instance in instances:
            old_data = old_data_map.get(instance.id, {})
            new_data = safe_model_to_dict(instance)
            changes = {}
            for field in fields:
                old_val = old_data.get(field)
                new_val = new_data.get(field)
                if str(old_val) != str(new_val):
                    changes[field] = {"old": str(old_val), "new": str(new_val)}

            if changes:
                create_audit_log_task.delay(
                    action="UPDATE",
                    model_name=model.__name__,
                    object_id=str(instance.external_id) if hasattr(instance, "external_id") else str(instance.pk),
                    changes=changes,
                    user_id=user.pk if user else None,
                    ip_address=None,
                    user_agent="GraphEngine/BulkUpdate"
                )

    def buffer_orphan(self, entity_type, missing_parent_id, payload, user=None, provider=None):
        from clinical.models import BufferedOrphan
        BufferedOrphan.objects.create(
            entity_type=entity_type,
            missing_parent_id=missing_parent_id,
            payload=payload,
            user=user,
            provider=provider
        )

    def resolve_orphans(self, parent_external_id):
        from clinical.models import BufferedOrphan
        from clinical.adapter import MultiVendorAdapter
        
        orphans = list(BufferedOrphan.objects.filter(missing_parent_id=parent_external_id))
        for orphan in orphans:
            try:
                with transaction.atomic():
                    req = type("DummyRequest", (object,), {"user": orphan.user, "provider": orphan.provider, "user_roles": ["cdisc"]})()
                    adapter = MultiVendorAdapter(orphan.provider)
                    adapter.sync_entity(req, orphan.entity_type, orphan.payload)
                    orphan.delete()
            except Exception as e:
                logger.warning(f"Orphan reprocessing failed for parent {parent_external_id}: {e}")

