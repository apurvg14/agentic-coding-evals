"""SWE-bench-style functional grader.

  FAIL_TO_PASS: tests that FAIL on the buggy workspace and must PASS after a
                correct fix (they prove the bug was actually fixed).
  PASS_TO_PASS: tests that already pass and must STAY passing (regression guard).

"Resolved" iff every FAIL_TO_PASS and PASS_TO_PASS test passes. Exit 0 = resolved.
The model never sees this file; the tests are the spec.
"""
import sys
sys.path.insert(0, ".")

from flatten import flatten

FAIL_TO_PASS = {
    "keeps_strings_intact": lambda: flatten(["ab", ["cd", "ef"]]) == ["ab", "cd", "ef"],
    "mixed_with_strings":   lambda: flatten([1, ["x", [2, "yz"]]]) == [1, "x", 2, "yz"],
    "single_string":        lambda: flatten(["hello"]) == ["hello"],
}

PASS_TO_PASS = {
    "deeply_nested_numbers": lambda: flatten([1, [2, [3, [4]]]]) == [1, 2, 3, 4],
    "already_flat":          lambda: flatten([1, 2, 3]) == [1, 2, 3],
    "tuples_too":            lambda: flatten([1, (2, 3), [4, (5,)]]) == [1, 2, 3, 4, 5],
    "empty_input":           lambda: flatten([]) == [],
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
