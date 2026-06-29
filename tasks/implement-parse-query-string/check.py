"""SWE-bench-style functional grader.

  FAIL_TO_PASS: tests that encode the spec. They fail on the unimplemented
                workspace and must pass after a correct implementation.
  PASS_TO_PASS: regression guard. Empty here: parse_qs() is a feature addition
                (the workspace raises NotImplementedError), so there is no
                pre-existing passing behavior to protect.

"Resolved" iff every FAIL_TO_PASS and PASS_TO_PASS test passes. Exit 0 = resolved.
The tests ARE the spec; the model never sees this file.
"""
import sys
sys.path.insert(0, ".")

from querystring import parse_qs

FAIL_TO_PASS = {
    "two_distinct_keys":   lambda: parse_qs("a=1&b=2") == {"a": "1", "b": "2"},
    "repeated_key_list":   lambda: parse_qs("a=1&a=2&a=3") == {"a": ["1", "2", "3"]},
    "empty_value":         lambda: parse_qs("k=") == {"k": ""},
    "empty_input":         lambda: parse_qs("") == {},
    "key_without_equals":  lambda: parse_qs("flag") == {"flag": ""},
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
