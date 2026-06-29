"""SWE-bench-style functional grader.

  FAIL_TO_PASS: tests that FAIL on the buggy workspace and must PASS after a
                correct fix (they prove the bug was actually fixed).
  PASS_TO_PASS: tests that already pass and must STAY passing (regression guard).

"Resolved" iff every FAIL_TO_PASS and PASS_TO_PASS test passes. Exit 0 = resolved.
The model never sees this file; the tests are the spec.
"""
import sys
sys.path.insert(0, ".")

from csvutil import parse_line

FAIL_TO_PASS = {
    "quoted_comma_field":     lambda: parse_line('a,"b,c",d') == ["a", "b,c", "d"],
    "whole_field_quoted":     lambda: parse_line('"x,y"') == ["x,y"],
    "multi_comma_in_quotes":  lambda: parse_line('1,"2,3,4",5') == ["1", "2,3,4", "5"],
}

PASS_TO_PASS = {
    "plain_three_fields":     lambda: parse_line("a,b,c") == ["a", "b", "c"],
    "single_field":           lambda: parse_line("single") == ["single"],
    "plain_two_fields":       lambda: parse_line("x,y") == ["x", "y"],
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
