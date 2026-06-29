"""SWE-bench-style functional grader.

  FAIL_TO_PASS: tests that encode the spec. They fail on the unimplemented
                workspace and must pass after a correct implementation.
  PASS_TO_PASS: regression guard. Empty here: is_valid() is a feature addition
                (the workspace raises NotImplementedError), so there is no
                pre-existing passing behavior to protect.

"Resolved" iff every FAIL_TO_PASS and PASS_TO_PASS test passes. Exit 0 = resolved.
The tests ARE the spec; the model never sees this file.
"""
import sys
sys.path.insert(0, ".")

from luhn import is_valid

FAIL_TO_PASS = {
    "classic_valid":     lambda: is_valid("79927398713") is True,
    "small_valid":       lambda: is_valid("1230") is True,
    "classic_invalid":   lambda: is_valid("79927398710") is False,
    "small_invalid":     lambda: is_valid("1231") is False,
}

PASS_TO_PASS = {}


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
