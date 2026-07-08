def merge_intervals(intervals):
    """Merge overlapping intervals into a sorted list of [start, end] pairs.

    The input may be in any order; intervals that overlap or merely touch
    (e.g. [1, 2] and [2, 3]) are combined.
    """
    if not intervals:
        return []
    ordered = sorted((list(iv) for iv in intervals), key=lambda iv: iv[0])
    result = [ordered[0]]
    for start, end in ordered[1:]:
        last = result[-1]
        if start <= last[1]:
            last[1] = max(last[1], end)
        else:
            result.append([start, end])
    return result
