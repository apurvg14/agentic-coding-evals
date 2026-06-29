"""SWE-bench-style functional grader.

  FAIL_TO_PASS: tests that FAIL on the buggy workspace and must PASS after a
                correct fix (they prove the bug was actually fixed).
  PASS_TO_PASS: tests that already pass and must STAY passing (regression guard).

"Resolved" iff every FAIL_TO_PASS and PASS_TO_PASS test passes. Exit 0 = resolved.
The model never sees this file; the tests are the spec.
"""
import sys
sys.path.insert(0, ".")

from paginate import page_offset, total_pages

FAIL_TO_PASS = {
    "first_page_offset_is_zero":   lambda: page_offset(1, 10) == 0,
    "second_page_offset":          lambda: page_offset(2, 10) == 10,
    "third_page_large_size":       lambda: page_offset(3, 25) == 50,
}

PASS_TO_PASS = {
    "no_items_zero_pages":         lambda: total_pages(0, 10) == 0,
    "exactly_one_page":            lambda: total_pages(10, 10) == 1,
    "partial_last_page":           lambda: total_pages(11, 10) == 2,
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
