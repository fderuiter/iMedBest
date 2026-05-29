class SyncRegistry:
    _registry = {}

    @classmethod
    def register(cls, entity_type, hierarchy_level, sync_func, schema_in, parent_type=None, parent_id_field=None):
        cls._registry[entity_type] = {
            'hierarchy_level': hierarchy_level,
            'sync_func': sync_func,
            'schema_in': schema_in,
            'parent_type': parent_type,
            'parent_id_field': parent_id_field
        }

    @classmethod
    def get(cls, entity_type):
        return cls._registry.get(entity_type)

    @classmethod
    def all(cls):
        return cls._registry

    @classmethod
    def get_order(cls):
        # Return entity types sorted by hierarchy level
        items = list(cls._registry.items())
        items.sort(key=lambda x: x[1]['hierarchy_level'])
        return {item[0]: item[1]['hierarchy_level'] for item in items}
