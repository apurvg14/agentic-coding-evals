"""SWE-bench-style functional grader.

  FAIL_TO_PASS: tests that FAIL on the buggy workspace and must PASS after a
                correct fix (they prove the bug was actually fixed).
  PASS_TO_PASS: tests that already pass and must STAY passing (regression guard).

"Resolved" iff every FAIL_TO_PASS and PASS_TO_PASS test passes. Exit 0 = resolved.
The model never sees this file; the tests are the spec.
"""
import sys
sys.path.insert(0, ".")

from ratelimit import TokenBucket


def burst_capped_after_idle():
    b = TokenBucket(2, 1)
    b.allow(0)
    b.allow(0)                                  # both starting tokens consumed
    allowed = sum(1 for _ in range(10) if b.allow(100))
    return allowed == 2                         # idle refill must cap at capacity


def idle_does_not_exceed_capacity():
    b = TokenBucket(3, 1)
    b.allow(0)                                  # 3 -> 2
    allowed = sum(1 for _ in range(5) if b.allow(1000))
    return allowed == 3


def fresh_bucket_allows_capacity():
    b = TokenBucket(3, 1)
    return sum(1 for _ in range(5) if b.allow(0)) == 3


def empty_bucket_denies():
    b = TokenBucket(1, 1)
    return b.allow(0) is True and b.allow(0) is False


def refill_over_time():
    b = TokenBucket(1, 1)
    b.allow(0)                                  # 1 -> 0
    return b.allow(1) is True                   # one unit of time -> one token


FAIL_TO_PASS = {
    "burst_capped_after_idle":      burst_capped_after_idle,
    "idle_does_not_exceed_capacity": idle_does_not_exceed_capacity,
}

PASS_TO_PASS = {
    "fresh_bucket_allows_capacity": fresh_bucket_allows_capacity,
    "empty_bucket_denies":          empty_bucket_denies,
    "refill_over_time":             refill_over_time,
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
