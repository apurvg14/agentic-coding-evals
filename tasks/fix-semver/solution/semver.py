def compare(a, b):
    """Compare two dotted semantic version strings like "1.10.0".

    Returns -1 if a < b, 0 if equal, 1 if a > b.
    """
    pa = [int(x) for x in a.split(".")]
    pb = [int(x) for x in b.split(".")]
    return (pa > pb) - (pa < pb)
