import copy


def deep_merge(a, b):
    """Return a new dict that is a deep merge of b into a.

    Nested dicts are merged recursively; for any other value type, b wins.
    Neither input is mutated.
    """
    result = copy.deepcopy(a)
    for key, b_val in b.items():
        if key in result and isinstance(result[key], dict) and isinstance(b_val, dict):
            result[key] = deep_merge(result[key], b_val)
        else:
            result[key] = copy.deepcopy(b_val)
    return result
