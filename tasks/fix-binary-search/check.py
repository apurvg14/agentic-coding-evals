"""SWE-bench-style functional grader.

  FAIL_TO_PASS: tests that FAIL on the buggy workspace and must PASS after a
                correct fix (they prove the bug was actually fixed).
  PASS_TO_PASS: tests that already pass and must STAY passing (regression guard).

"Resolved" iff every FAIL_TO_PASS and PASS_TO_PASS test passes. Exit 0 = resolved.
The model never sees this file; the tests are the spec.
"""
import sys
sys.path.insert(0, ".")

from search import first_index

FAIL_TO_PASS = {
    "leftmost_of_duplicates":   lambda: first_index([1, 2, 2, 2, 3], 2) == 1,
    "all_equal_returns_zero":   lambda: first_index([2, 2, 2], 2) == 0,
    "leftmost_at_start":        lambda: first_index([1, 1, 1, 1], 1) == 0,
}

PASS_TO_PASS = {
    "unique_middle":            lambda: first_index([1, 2, 3], 2) == 1,
    "absent_returns_minus_one": lambda: first_index([1, 2, 3], 4) == -1,
    "empty_list":               lambda: first_index([], 5) == -1,
    "single_match":             lambda: first_index([5], 5) == 0,
    "first_element_unique":     lambda: first_index([1, 2, 3], 1) == 0,
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
