"""SWE-bench-style functional grader.

  FAIL_TO_PASS: tests that encode the spec. They fail on the unimplemented
                workspace and must pass after a correct implementation.
  PASS_TO_PASS: regression guard. Empty here: to_roman() is a feature addition
                (the workspace raises NotImplementedError), so there is no
                pre-existing passing behavior to protect.

"Resolved" iff every FAIL_TO_PASS and PASS_TO_PASS test passes. Exit 0 = resolved.
The tests ARE the spec; the model never sees this file.
"""
import sys
sys.path.insert(0, ".")

from roman import to_roman

FAIL_TO_PASS = {
    "one_is_I":            lambda: to_roman(1) == "I",
    "three_is_III":        lambda: to_roman(3) == "III",
    "four_is_IV":          lambda: to_roman(4) == "IV",
    "nine_is_IX":          lambda: to_roman(9) == "IX",
    "fifty_eight":         lambda: to_roman(58) == "LVIII",
    "forty_is_XL":         lambda: to_roman(40) == "XL",
    "ninety_four":         lambda: to_roman(94) == "XCIV",
    "complex_1994":        lambda: to_roman(1994) == "MCMXCIV",
    "max_3999":            lambda: to_roman(3999) == "MMMCMXCIX",
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
