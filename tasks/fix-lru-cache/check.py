"""SWE-bench-style functional grader.

  FAIL_TO_PASS: tests that FAIL on the buggy workspace and must PASS after a
                correct fix (they prove the bug was actually fixed).
  PASS_TO_PASS: tests that already pass and must STAY passing (regression guard).

"Resolved" iff every FAIL_TO_PASS and PASS_TO_PASS test passes. Exit 0 = resolved.
The model never sees this file; the tests are the spec.
"""
import sys
sys.path.insert(0, ".")

from lru import LRUCache


def access_protects_from_eviction():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.get("a")        # 'a' becomes most-recently used
    c.put("c", 3)     # capacity 2 -> evict LRU, which is 'b'
    return c.get("a") == 1 and c.get("b") is None and c.get("c") == 3


def update_refreshes_recency():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("a", 10)    # updating 'a' also makes it most-recently used
    c.put("c", 3)     # evict LRU, which is now 'b'
    return c.get("a") == 10 and c.get("b") is None and c.get("c") == 3


def basic_get_put():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    return c.get("a") == 1 and c.get("b") == 2


def missing_key_returns_none():
    c = LRUCache(2)
    return c.get("nope") is None


def capacity_is_respected():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)     # no gets: plain insertion-order eviction drops 'a'
    return len(c.store) == 2 and c.get("c") == 3


FAIL_TO_PASS = {
    "access_protects_from_eviction": access_protects_from_eviction,
    "update_refreshes_recency":      update_refreshes_recency,
}

PASS_TO_PASS = {
    "basic_get_put":          basic_get_put,
    "missing_key_returns_none": missing_key_returns_none,
    "capacity_is_respected":  capacity_is_respected,
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
