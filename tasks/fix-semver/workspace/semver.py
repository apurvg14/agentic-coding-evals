def compare(a, b):
    """Compare two dotted semantic version strings like "1.10.0".

    Returns -1 if a < b, 0 if equal, 1 if a > b.
    """
    return (a > b) - (a < b)
