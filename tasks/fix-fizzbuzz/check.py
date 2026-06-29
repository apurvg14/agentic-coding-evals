"""SWE-bench-style functional grader.

  FAIL_TO_PASS: tests that FAIL on the buggy workspace and must PASS after a
                correct fix (they prove the bug was actually fixed).
  PASS_TO_PASS: tests that already pass and must STAY passing (regression guard).

"Resolved" iff every FAIL_TO_PASS and PASS_TO_PASS test passes. Exit 0 = resolved.
The model never sees this file; the tests are the spec.
"""
import sys
sys.path.insert(0, ".")

from fizzbuzz import fizzbuzz

FAIL_TO_PASS = {
    "multiple_of_15_is_FizzBuzz":      lambda: fizzbuzz(15)[14] == "FizzBuzz",
    "multiple_of_30_is_FizzBuzz":      lambda: fizzbuzz(30)[29] == "FizzBuzz",
    "only_15s_and_30s_are_FizzBuzz":   lambda: [i for i, v in enumerate(fizzbuzz(30), 1)
                                                if v == "FizzBuzz"] == [15, 30],
}

PASS_TO_PASS = {
    "length_matches_n":                lambda: len(fizzbuzz(15)) == 15,
    "plain_number":                    lambda: fizzbuzz(15)[0] == "1",
    "multiple_of_3_is_Fizz":           lambda: fizzbuzz(15)[2] == "Fizz",
    "multiple_of_5_is_Buzz":           lambda: fizzbuzz(15)[4] == "Buzz",
    "9_is_Fizz_and_10_is_Buzz":        lambda: fizzbuzz(15)[8] == "Fizz" and fizzbuzz(15)[9] == "Buzz",
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
