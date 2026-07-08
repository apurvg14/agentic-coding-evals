"""SWE-bench-style functional grader.

  FAIL_TO_PASS: tests that FAIL on the buggy workspace and must PASS after a
                correct fix (they prove the bug was actually fixed).
  PASS_TO_PASS: tests that already pass and must STAY passing (regression guard).

"Resolved" iff every FAIL_TO_PASS and PASS_TO_PASS test passes. Exit 0 = resolved.
The model never sees this file; the tests are the spec.
"""
import sys
sys.path.insert(0, ".")

from intervals import merge_intervals

FAIL_TO_PASS = {
    "touching_intervals_merge":   lambda: merge_intervals([[1, 2], [2, 3]]) == [[1, 3]],
    "unsorted_input":             lambda: merge_intervals([[3, 5], [1, 4]]) == [[1, 5]],
    "unsorted_and_touching":      lambda: merge_intervals([[1, 2], [5, 6], [2, 5]]) == [[1, 6]],
}

PASS_TO_PASS = {
    "disjoint_unchanged":         lambda: merge_intervals([[1, 2], [5, 6]]) == [[1, 2], [5, 6]],
    "simple_overlap":             lambda: merge_intervals([[1, 3], [2, 5]]) == [[1, 5]],
    "nested_interval":            lambda: merge_intervals([[1, 4], [2, 3]]) == [[1, 4]],
    "empty_input":                lambda: merge_intervals([]) == [],
    "single_interval":            lambda: merge_intervals([[1, 10]]) == [[1, 10]],
}


def _evaluate(group):
    out = {}
    for name, fn in group.items():
        try:
            out[name] = bool(fn())
        except Exception:  # a raising test counts as a failure
            out[name] = False
    return out


def main():
    f2p = _evaluate(FAIL_TO_PASS)
    p2p = _evaluate(PASS_TO_PASS)
    resolved = all(f2p.values()) and all(p2p.values())
    print("FAIL_TO_PASS:", f2p)
    print("PASS_TO_PASS:", p2p)
    print("RESOLVED" if resolved else "UNRESOLVED")
    sys.exit(0 if resolved else 1)


main()
