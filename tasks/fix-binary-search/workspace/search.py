def first_index(xs, target):
    """Return the index of the FIRST (leftmost) occurrence of target in the
    sorted list xs, or -1 if target is not present."""
    lo, hi = 0, len(xs) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if xs[mid] == target:
            return mid
        elif xs[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
