"""SWE-bench-style functional grader.

  FAIL_TO_PASS: tests that FAIL on the buggy workspace and must PASS after a
                correct fix (they prove the bug was actually fixed).
  PASS_TO_PASS: tests that already pass and must STAY passing (regression guard).

"Resolved" iff every FAIL_TO_PASS and PASS_TO_PASS test passes. Exit 0 = resolved.
The model never sees this file; the tests are the spec.
"""
import sys
sys.path.insert(0, ".")

from semver import compare

FAIL_TO_PASS = {
    "ten_is_greater_than_nine":    lambda: compare("1.10.0", "1.9.0") == 1,
    "two_is_less_than_ten":        lambda: compare("2.0.0", "10.0.0") == -1,
    "patch_numeric_order":         lambda: compare("1.0.10", "1.0.9") == 1,
}

PASS_TO_PASS = {
    "equal_versions":              lambda: compare("1.0.0", "1.0.0") == 0,
    "simple_patch_less":           lambda: compare("0.0.1", "0.0.2") == -1,
    "simple_minor_greater":        lambda: compare("1.2.0", "1.1.0") == 1,
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
