from django.apps import apps

from .models import BufferedOrphan


class MultiVendorAdapter:
    def __init__(self, provider):
        self.provider = provider
        # Defaults if mappings are empty
        self.hierarchy_mapping = provider.hierarchy_mapping if provider and provider.hierarchy_mapping else {}
        self.schema_mapping = provider.schema_mapping if provider and provider.schema_mapping else {}

    def resolve_entity_type(self, raw_type):
        """Map external entity type to internal model name."""
        return self.hierarchy_mapping.get(raw_type, raw_type)

    def map_payload(self, raw_type, payload):
        """Map external payload keys to internal payload keys."""
        type_mapping = self.schema_mapping.get(raw_type, {})
        mapped = {}
        for k, v in payload.items():
            if k in type_mapping:
                mapped[type_mapping[k]] = v
            else:
                mapped[k] = v
        return mapped

    def get_parent_field_for_model(self, model_name):
        model_name = model_name.lower()
        mapping = {
            "site": "study",
            "subject": "site",
            "form": "study",
            "interval": "study",
            "variable": "form",
            "visit": ["subject", "interval"],
            "record": ["visit", "variable"],
            "coding": "record",
            "query": "record",
            "recordrevision": "record",
        }
        return mapping.get(model_name)

    def sync_entity(self, request, raw_type, payload):
        entity_type = self.resolve_entity_type(raw_type)
        mapped_payload = self.map_payload(raw_type, payload)

        try:
            ModelCls = apps.get_model("clinical", entity_type)
        except LookupError as err:
            raise ValueError(f"Unknown entity type: {entity_type}") from err

        parent_fields = self.get_parent_field_for_model(entity_type)

        defaults = {
            "updated_by": request.user,
        }

        # Additional scalar fields depending on model
        for field in ["clinical_timestamp", "source_sequence", "name", "value", "code", "text", "contains_phi"]:
            if field in mapped_payload:
                val = mapped_payload[field]
                if field == "clinical_timestamp" and val and isinstance(val, str):
                    from django.utils.dateparse import parse_datetime

                    parsed_val = parse_datetime(val)
                    # Only set clinical_timestamp if parsing succeeded
                    if parsed_val:
                        defaults[field] = parsed_val
                    # If parse_datetime returns None, skip assignment to avoid overwriting existing timestamp
                else:
                    defaults[field] = val

        # Resolve parents dynamically
        if parent_fields:
            if isinstance(parent_fields, str):
                parent_fields = [parent_fields]

            for parent_field in parent_fields:
                parent_ext_id_key = f"{parent_field}_ext_id"
                # Check mapping for parent ext id key
                mapped_parent_ext_id_key = self.schema_mapping.get(raw_type, {}).get(
                    parent_ext_id_key, parent_ext_id_key
                )

                parent_ext_id = mapped_payload.get(mapped_parent_ext_id_key)
                if not parent_ext_id:
                    # try without mapping
                    parent_ext_id = mapped_payload.get(parent_ext_id_key)

                if parent_ext_id:
                    ParentModelCls = ModelCls._meta.get_field(parent_field).related_model
                    # Access check
                    parent_qs = ParentModelCls.objects.filter(provider=self.provider, external_id=parent_ext_id)
                    parent_obj = parent_qs.first()

                    if not parent_obj:
                        BufferedOrphan.objects.create(
                            entity_type=raw_type,
                            missing_parent_id=parent_ext_id,
                            payload=payload,
                            user=request.user,
                            provider=self.provider,
                        )
                        return 202, {"message": "Buffered due to missing parent"}
                    defaults[parent_field] = parent_obj

        # Sync
        obj, _ = ModelCls.objects.update_or_create(
            provider=self.provider,
            external_id=mapped_payload.get("external_id"),
            defaults=defaults,
            create_defaults={**defaults, "created_by": request.user},
        )

        from .api import check_and_process_orphans

        check_and_process_orphans(obj.external_id)

        return obj
