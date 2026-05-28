import json
from uuid import UUID
from datetime import datetime
from django.forms.models import model_to_dict

def get_hierarchical_batch(instance):
    """
    Returns a list of dictionaries representing the instance and its hierarchical ancestors,
    ordered from root to the child instance.
    """
    from clinical.models import ClinicalEntity
    
    entities = []
    
    def traverse(obj):
        if not obj or not isinstance(obj, ClinicalEntity):
            return
        
        # Avoid circular dependencies, just in case
        if any(e['id'] == str(obj.pk) and e['type'] == obj.__class__.__name__ for e in entities):
            return
            
        # Get all related parents
        # ForeignKeys usually indicate parent relationship
        for field in obj._meta.fields:
            if field.is_relation and field.many_to_one:
                parent = getattr(obj, field.name, None)
                if parent:
                    traverse(parent)
                    
        # After traversing parents, add self
        # Prevent duplicates
        if not any(e['id'] == str(obj.pk) and e['type'] == obj.__class__.__name__ for e in entities):
            data = {}
            for field in obj._meta.fields:
                val = getattr(obj, field.name)
                # Serialize special types
                if isinstance(val, UUID):
                    data[field.name] = str(val)
                elif hasattr(val, 'isoformat'):
                    data[field.name] = val.isoformat()
                elif hasattr(val, 'pk'):  # ForeignKey
                    data[field.name] = str(val.pk)
                else:
                    data[field.name] = val
                    
            # Add some metadata
            payload = {
                "type": obj.__class__.__name__,
                "id": str(obj.pk),
                "data": data,
                "external_id": getattr(obj, 'external_id', None)
            }
            entities.append(payload)

    traverse(instance)
    
    # Sort them loosely (the recursion is basically a DFS and parents are visited before self, so it's already sorted root-first)
    return entities
