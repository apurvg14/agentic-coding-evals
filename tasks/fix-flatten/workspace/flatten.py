def flatten(items):
    """Recursively flatten a nested structure into a flat list."""
    result = []
    for item in items:
        try:
            iter(item)
            result.extend(flatten(item))
        except TypeError:
            result.append(item)
    return result
