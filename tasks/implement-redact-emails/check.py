"""SWE-bench-style functional grader.

  FAIL_TO_PASS: tests that encode the spec. They fail on the unimplemented
                workspace and must pass after a correct implementation.
  PASS_TO_PASS: regression guard. Empty here: redact() is a feature addition
                (the workspace raises NotImplementedError), so there is no
                pre-existing passing behavior to protect.

"Resolved" iff every FAIL_TO_PASS and PASS_TO_PASS test passes. Exit 0 = resolved.
The tests ARE the spec; the model never sees this file.
"""
import sys
sys.path.insert(0, ".")

from redact import redact

FAIL_TO_PASS = {
    "single_email_in_sentence": lambda: redact("contact me at john@example.com please") == "contact me at [redacted] please",
    "two_emails":               lambda: redact("a@b.com, c@d.org") == "[redacted], [redacted]",
    "no_email_unchanged":       lambda: redact("no emails here") == "no emails here",
    "dotted_plus_subdomain":    lambda: redact("dotted.name+tag@sub.domain.co") == "[redacted]",
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
