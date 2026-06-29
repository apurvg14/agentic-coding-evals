"""SWE-bench-style functional grader.

  FAIL_TO_PASS: tests that encode the spec. They fail on the unimplemented
                workspace and must pass after a correct implementation.
  PASS_TO_PASS: regression guard. Empty here: deep_merge() is a feature addition
                (the workspace raises NotImplementedError), so there is no
                pre-existing passing behavior to protect.

"Resolved" iff every FAIL_TO_PASS and PASS_TO_PASS test passes. Exit 0 = resolved.
The tests ARE the spec; the model never sees this file.
"""
import sys
sys.path.insert(0, ".")

from dictutil import deep_merge


def does_not_mutate_inputs():
    a = {"a": {"b": 1}}
    b = {"a": {"c": 2}}
    deep_merge(a, b)
    return a == {"a": {"b": 1}} and b == {"a": {"c": 2}}


FAIL_TO_PASS = {
    "merges_disjoint_keys":   lambda: deep_merge({"x": 1}, {"y": 2}) == {"x": 1, "y": 2},
    "merges_nested_dicts":    lambda: deep_merge({"a": {"b": 1}}, {"a": {"c": 2}}) == {"a": {"b": 1, "c": 2}},
    "b_overrides_scalar":     lambda: deep_merge({"a": 1}, {"a": 2}) == {"a": 2},
    "scalar_overrides_dict":  lambda: deep_merge({"a": {"b": 1}}, {"a": 5}) == {"a": 5},
    "does_not_mutate_inputs": does_not_mutate_inputs,
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
