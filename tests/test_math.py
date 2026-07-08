"""Unit tests for the math word-problem suite.

Pure in-process (no server, no API key, no browser): they exercise the numeric
grader, the answer-preserving perturbations, dataset loading, and the keyless
reference/brittle backends through the real run loop + report engine.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from agenteval import matheval, mathdata, report

SAMPLE = mathdata.load_dataset("sample")


def test_sample_loads():
    assert len(SAMPLE) == 10
    assert all(p.perturbation == "clean" for p in SAMPLE)
    assert SAMPLE[0].id == "math-1" and SAMPLE[0].answer == 12.0


@pytest.mark.parametrize("text,gold", [
    ("Answer: 18", 18),
    ("The total works out to 18.0.", 18),
    ("It costs $1,234 in the end", 1234),
    ("Answer: -5", -5),
    ("We add 3 then 7, so Answer: 10", 10),
])
def test_grader_accepts_correct(text, gold):
    assert matheval.is_correct(text, gold)


def test_grader_rejects_and_handles_missing():
    assert not matheval.is_correct("Answer: 19", 18)
    assert matheval.extract_answer("no numbers here at all") is None
    assert not matheval.is_correct("no numbers", 5)


def test_parse_gold_variants():
    assert mathdata.parse_gold("Reasoning... #### 42") == 42.0
    assert mathdata.parse_gold("1,000") == 1000.0
    assert mathdata.parse_gold(7) == 7.0


def test_perturbations_are_label_preserving_and_effective():
    q = "John earns $9 per hour and finished 60% of the shift."
    assert "Michael" in matheval.apply_atom("name_swap", q)
    reformatted = matheval.apply_atom("reformat", q)
    assert "9 dollars" in reformatted and "60 percent" in reformatted
    assert "13 birds" in matheval.apply_atom("distractor", q)
    assert matheval.apply_atom("paraphrase", q) != q  # control still reworded
    # none of these change the numbers that determine the answer
    for atom in matheval.MATH_ATOMS:
        assert isinstance(matheval.apply_atom(atom, q), str)


def _summary_for(model):
    out = Path(tempfile.mkdtemp(prefix="mathtest-"))
    current = matheval.run_math_suite(model, SAMPLE, out,
                                      results_path=out / "m.json", resume=False)
    return report.summarize(current, atoms=matheval.atoms_for(SAMPLE))


def test_reference_backend_is_robust():
    row = next(m for m in _summary_for("reference")["models"] if m["model"] == "reference")
    assert row["clean_pass"] == 100.0
    assert row["robust_pass"] == 100.0
    assert row["asr"] == 0.0


def test_brittle_backend_is_broken_by_its_perturbations():
    s = _summary_for("brittle-a")
    row = next(m for m in s["models"] if m["model"] == "brittle-a")
    assert row["clean_pass"] == 100.0
    assert row["robust_pass"] == 0.0
    fc = {f["atom"]: f["counts"]["brittle-a"] for f in s["failure_classes"]}
    assert fc["distractor"] == 10  # attack breaks every clean-solved problem
    assert fc["paraphrase"] == 0   # control breaks nothing


@pytest.mark.parametrize("name", ["gsm8k", "svamp"])
def test_bundled_public_slices_load_and_grade(name):
    # Real public-dataset problems ship in-repo; confirm they parse to numeric
    # gold answers and flow through the grader (reference solves them robustly).
    probs = mathdata.load_dataset(name, limit=5)
    assert len(probs) == 5
    assert all(isinstance(p.answer, float) for p in probs)
    out = Path(tempfile.mkdtemp(prefix="mathreal-"))
    current = matheval.run_math_suite("reference", probs, out,
                                      results_path=out / "m.json", resume=False)
    row = next(m for m in report.summarize(current)["models"] if m["model"] == "reference")
    assert row["clean_pass"] == 100.0 and row["robust_pass"] == 100.0
