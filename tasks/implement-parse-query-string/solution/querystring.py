def parse_qs(s):
    """Parse a URL query string like 'a=1&b=2&a=3' into a dict.

    A key that appears once maps to a single string value. A key that appears
    more than once maps to a list of its values, in order. A pair with no '='
    maps the key to an empty string. An empty input yields an empty dict.
    """
    result = {}
    if not s:
        return result
    for pair in s.split("&"):
        if "=" in pair:
            key, value = pair.split("=", 1)
        else:
            key, value = pair, ""
        if key in result:
            if isinstance(result[key], list):
                result[key].append(value)
            else:
                result[key] = [result[key], value]
        else:
            result[key] = value
    return result
