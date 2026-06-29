"""SWE-bench-style functional grader.

  FAIL_TO_PASS: tests that FAIL on the buggy workspace and must PASS after a
                correct fix (they prove the bug was actually fixed).
  PASS_TO_PASS: tests that already pass and must STAY passing (regression guard).

"Resolved" iff every FAIL_TO_PASS and PASS_TO_PASS test passes. Exit 0 = resolved.
The model never sees this file; the tests are the spec.
"""
import sys
sys.path.insert(0, ".")

from stats import median

FAIL_TO_PASS = {
    "even_len_averages_two_middles":   lambda: median([1, 2, 3, 4]) == 2.5,
    "even_len_unsorted":               lambda: median([10, 2, 8, 4]) == 6,
    "even_len_two_elements":           lambda: median([1, 4]) == 2.5,
}

PASS_TO_PASS = {
    "odd_len_unsorted":                lambda: median([1, 3, 2]) == 2,
    "single_element":                  lambda: median([5]) == 5,
    "odd_len_three":                   lambda: median([7, 1, 3]) == 3,
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
