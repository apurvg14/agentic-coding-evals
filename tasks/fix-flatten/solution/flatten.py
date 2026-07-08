def flatten(items):
    """Recursively flatten nested lists/tuples into a flat list.

    Strings (and other non-list/tuple values) are treated as atomic and are
    appended as-is rather than being iterated into.
    """
    result = []
    for item in items:
        if isinstance(item, (list, tuple)):
            result.extend(flatten(item))
        else:
            result.append(item)
    return result
