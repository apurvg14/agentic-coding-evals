"""SWE-bench-style functional grader.

  FAIL_TO_PASS: tests that FAIL on the buggy workspace and must PASS after a
                correct implementation (they encode the spec).
  PASS_TO_PASS: regression guard. Empty here: slugify() is a feature addition
                (the workspace raises NotImplementedError), so there is no
                pre-existing passing behavior to protect.

The tests ARE the spec: lowercase; every run of non-alphanumerics collapses to a
single hyphen; strip leading/trailing hyphens. Exit 0 = resolved. The model never
sees this file.
"""
import sys
sys.path.insert(0, ".")

from textutil import slugify

FAIL_TO_PASS = {
    "basic_punctuation":      lambda: slugify("Hello, World!") == "hello-world",
    "collapse_spaces":        lambda: slugify("  Multiple   spaces ") == "multiple-spaces",
    "already_a_slug":         lambda: slugify("already-slug") == "already-slug",
    "underscores_to_hyphen":  lambda: slugify("Under_scores_too") == "under-scores-too",
    "mixed_punctuation":      lambda: slugify("Node.js / React & Vue!") == "node-js-react-vue",
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
