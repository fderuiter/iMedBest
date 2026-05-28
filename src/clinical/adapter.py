from .models import Provider, Study, Site, Subject, Form, Interval, Variable, Visit, Record, Coding, Query, RecordRevision
from django.shortcuts import get_object_or_404

class HierarchyAdapter:
    def __init__(self, provider):
        self.provider = provider
        # Default mapping assumes the current hardcoded API schema
        self.mapping = {
            'Site': {'parent_field': 'study', 'parent_model': Study, 'external_key': 'study_ext_id'},
            'Subject': {'parent_field': 'site', 'parent_model': Site, 'external_key': 'site_ext_id'},
            'Form': {'parent_field': 'study', 'parent_model': Study, 'external_key': 'study_ext_id'},
            'Interval': {'parent_field': 'study', 'parent_model': Study, 'external_key': 'study_ext_id'},
            'Variable': {'parent_field': 'form', 'parent_model': Form, 'external_key': 'form_ext_id'},
            # Visit needs 2 parents: subject, interval
            'Visit': {'parents': [
                {'parent_field': 'subject', 'parent_model': Subject, 'external_key': 'subject_ext_id'},
                {'parent_field': 'interval', 'parent_model': Interval, 'external_key': 'interval_ext_id'}
            ]},
            'Record': {'parents': [
                {'parent_field': 'visit', 'parent_model': Visit, 'external_key': 'visit_ext_id'},
                {'parent_field': 'variable', 'parent_model': Variable, 'external_key': 'variable_ext_id'}
            ]},
            'Coding': {'parent_field': 'record', 'parent_model': Record, 'external_key': 'record_ext_id'},
            'Query': {'parent_field': 'record', 'parent_model': Record, 'external_key': 'record_ext_id'},
            'RecordRevision': {'parent_field': 'record', 'parent_model': Record, 'external_key': 'record_ext_id'},
        }

        # Override with provider's mapping
        if self.provider and isinstance(self.provider.hierarchy_mapping, dict):
            for k, v in self.provider.hierarchy_mapping.items():
                if k in self.mapping:
                    self.mapping[k].update(v)

    def get_parents(self, entity_type, payload):
        parents = {}
        mapping_info = self.mapping.get(entity_type)
        if not mapping_info:
            return parents
        
        if 'parents' in mapping_info:
            for parent_info in mapping_info['parents']:
                ext_key = parent_info['external_key']
                parent_model = parent_info['parent_model']
                parent_field = parent_info['parent_field']
                ext_id = getattr(payload, ext_key, None)
                if ext_id is None and isinstance(payload, dict):
                    ext_id = payload.get(ext_key)
                if ext_id:
                    # filter by provider as well!
                    parents[parent_field] = get_object_or_404(parent_model, external_id=ext_id, provider=self.provider)
        else:
            ext_key = mapping_info['external_key']
            parent_model = mapping_info['parent_model']
            parent_field = mapping_info['parent_field']
            ext_id = getattr(payload, ext_key, None)
            if ext_id is None and isinstance(payload, dict):
                ext_id = payload.get(ext_key)
            if ext_id:
                parents[parent_field] = get_object_or_404(parent_model, external_id=ext_id, provider=self.provider)
        return parents
