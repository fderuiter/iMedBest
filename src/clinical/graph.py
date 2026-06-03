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

    # Create a mapping of id(entity) to entity, and a graph
    # Actually, we can just sort by depths. Let's calculate depths dynamically.
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

    # Sort entities by their computed depth
    # If same depth, maintain original order
    return sorted(entities, key=lambda e: depths.get(e.entity_type, 99))
