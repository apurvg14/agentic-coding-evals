"""SWE-bench-style functional grader.

  FAIL_TO_PASS: tests that FAIL on the buggy workspace and must PASS after a
                correct fix (they prove the bug was actually fixed).
  PASS_TO_PASS: tests that already pass and must STAY passing (regression guard).

"Resolved" iff every FAIL_TO_PASS and PASS_TO_PASS test passes. Exit 0 = resolved.
The model never sees this file; the tests are the spec.
"""
import sys
sys.path.insert(0, ".")

from datemath import add_days

FAIL_TO_PASS = {
    "leap_feb_29_exists_2024":    lambda: add_days(2024, 2, 28, 1) == (2024, 2, 29),
    "leap_feb_29_exists_2000":    lambda: add_days(2000, 2, 28, 1) == (2000, 2, 29),
    "leap_feb_span_two_days":     lambda: add_days(2024, 2, 27, 2) == (2024, 2, 29),
}

PASS_TO_PASS = {
    "non_leap_feb_rolls_to_mar":  lambda: add_days(2023, 2, 28, 1) == (2023, 3, 1),
    "month_rollover":             lambda: add_days(2023, 1, 31, 1) == (2023, 2, 1),
    "year_rollover":              lambda: add_days(2023, 12, 31, 1) == (2024, 1, 1),
    "simple_same_month":          lambda: add_days(2023, 3, 10, 5) == (2023, 3, 15),
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
