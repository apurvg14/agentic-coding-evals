import sys
sys.path.insert(0, ".")
from textutil import slugify

cases = {
    "Hello, World!": "hello-world",
    "  Multiple   spaces ": "multiple-spaces",
    "already-slug": "already-slug",
    "Under_scores_too": "under-scores-too",
    "AI/ML & PM": "ai-ml-pm",
}
for inp, want in cases.items():
    got = slugify(inp)
    assert got == want, f"slugify({inp!r}) = {got!r}, want {want!r}"
print("ok")
