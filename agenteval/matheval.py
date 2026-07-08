"""Adversarial-robustness eval for math word problems.

Same methodology as the coding suite, one domain over: take a problem whose gold
answer is known, apply a **semantics-preserving perturbation** (the answer never
changes), and check whether the model's answer flips. A model that truly reasons
should be invariant; a pattern-matcher is not.

Two modes:
  synth     (gsm8k / svamp / the bundled sample: clean seeds) -- for each problem
            we synthesize single perturbations from MATH_ATOMS and sweep them.
  provided  (datasets that already ship answer-preserving variants grouped by a
            seed, e.g. GSM-Plus) -- we run each provided variant as-is and use its
            perturbation label as the attack.

Grading is numeric: we extract the final number from the model's reply (preferring
an explicit "Answer: N" line, else the last number) and compare to the gold with a
small tolerance -- never string-matching the prose. Infrastructure errors are
retried and excluded, exactly as in the coding runner.

Records are emitted in the SAME schema as the coding runner, so report.py computes
clean/robust accuracy, per-perturbation attribution and cross-model transfer with
no changes.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from . import agent
from .mathdata import MathProblem

# paraphrase is the control (should not break); the rest are attacks.
MATH_ATOMS = ["paraphrase", "verbose", "distractor", "noop", "name_swap", "reformat"]

# Keyless demo backends for offline runs/tests. Share `distractor` (transfers)
# but differ otherwise (those attacks do NOT transfer) -- mirrors the coding demo.
MATH_BRITTLE = {
    "brittle-a": {"distractor", "name_swap"},
    "brittle-b": {"distractor", "verbose"},
}

_NAME_MAP = {
    "John": "Michael", "Mary": "Sarah", "Liam": "Ethan", "Maria": "Sofia",
    "Noah": "Oliver", "Emma": "Ava", "Olivia": "Mia", "James": "Daniel",
    "Sarah": "Rachel", "Tom": "Greg",
}


# ----- perturbations (answer-preserving) ------------------------------------
def _name_swap(q: str) -> str:
    def repl(m):
        return _NAME_MAP.get(m.group(0), m.group(0))
    return re.sub(r"\b(" + "|".join(map(re.escape, _NAME_MAP)) + r")\b", repl, q)


def _reformat(q: str) -> str:
    q = re.sub(r"\$(\d+(?:\.\d+)?)", r"\1 dollars", q)
    q = re.sub(r"(\d+(?:\.\d+)?)%", r"\1 percent", q)
    return q


def _distractor(q: str) -> str:
    return (q + " Also, there were 13 birds resting on a nearby fence at the time, "
            "which has nothing to do with the question.")


def _noop(q: str) -> str:
    return q + " Note that this problem was reviewed twice for clarity before publishing."


def _verbose(q: str) -> str:
    pre = ("Background (mostly not needed): this question comes from a large practice "
           "set that is updated every semester and reviewed by several tutors. None of "
           "that affects the math. Here is the actual problem.\n\n")
    post = "\n\nThere is no trick here; just compute the requested quantity."
    return pre + q + post


def _paraphrase(q: str) -> str:  # control
    return "Please solve the following word problem carefully.\n\n" + q


_ATOM_FN = {
    "name_swap": _name_swap, "reformat": _reformat, "distractor": _distractor,
    "noop": _noop, "verbose": _verbose, "paraphrase": _paraphrase,
}

_NOTES = {
    "paraphrase": "faithful reword (control)",
    "verbose": "real problem buried in irrelevant-but-true context",
    "distractor": "an irrelevant numeric fact is appended",
    "noop": "a seemingly-relevant but inconsequential clause is appended",
    "name_swap": "proper names are swapped",
    "reformat": "number formatting rephrased ($5 -> 5 dollars, 60% -> 60 percent)",
}


def apply_atom(atom: str, question: str) -> str:
    return _ATOM_FN[atom](question) if atom else question


def atoms_for(problems: list[MathProblem]) -> list[str]:
    """Perturbation labels to report on: provided variants' types, else MATH_ATOMS."""
    provided = sorted({p.perturbation for p in problems if p.perturbation != "clean"})
    return provided if provided else list(MATH_ATOMS)


# ----- numeric grading -------------------------------------------------------
def extract_answer(text: str) -> float | None:
    """Final number from a model reply: prefer 'Answer: N', else the last number."""
    t = text.replace(",", "")
    m = re.findall(r"[Aa]nswer\s*[:=]?\s*\$?(-?\d+(?:\.\d+)?)", t)
    if m:
        return float(m[-1])
    nums = re.findall(r"-?\d+(?:\.\d+)?", t)
    return float(nums[-1]) if nums else None


def is_correct(pred_text: str, gold: float, tol: float = 1e-4) -> bool:
    pred = extract_answer(pred_text)
    return pred is not None and abs(pred - gold) <= tol


def _fmt_gold(g: float) -> str:
    return str(int(g)) if abs(g - round(g)) < 1e-9 else str(g)


# ----- backends --------------------------------------------------------------
def _answer(model: str, question: str, gold: float, atom: str) -> str:
    if model == "reference":
        return f"Answer: {_fmt_gold(gold)}"
    if model in MATH_BRITTLE:
        if atom and atom in MATH_BRITTLE[model]:
            return f"Answer: {_fmt_gold(gold + 1)}"  # deterministically wrong
        return f"Answer: {_fmt_gold(gold)}"
    return agent.answer_question(model, question)


# ----- checkpointing (mirrors runner.py) ------------------------------------
def _combo_key(combo) -> str:
    return "+".join(combo) if combo else "clean"


def _atomic_write_json(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    # os.replace can transiently fail on Windows if the target is momentarily
    # locked (AV/indexer); retry briefly before giving up.
    for attempt in range(10):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.05 * (attempt + 1))
    os.replace(tmp, path)


def _run_one(problem: MathProblem, model: str, atom: str, out_dir: Path,
             max_retries: int = 3, apply_perturbation: bool = True) -> dict:
    # In "provided" mode the variant text already carries the perturbation, so we
    # record the atom but do not re-apply it.
    question = apply_atom(atom, problem.question) if (atom and apply_perturbation) else problem.question
    combo = [atom] if atom else []
    status, error, pred_text = "ok", "", ""
    t0 = time.time()
    for attempt in range(1, max_retries + 2):
        try:
            pred_text = _answer(model, question, problem.answer, atom)
            status, error = "ok", ""
            break
        except Exception as e:  # noqa: BLE001 - classify infra vs. genuine
            error = f"{type(e).__name__}: {e}"
            if agent.is_transient_error(e) and attempt <= max_retries:
                time.sleep(min(2 ** attempt, 20))
                continue
            status = "error"
            break

    passed = None if status == "error" else is_correct(pred_text, problem.answer)
    elapsed = round(time.time() - t0, 2)

    tdir = out_dir / "math_transcripts"
    tdir.mkdir(parents=True, exist_ok=True)
    tpath = tdir / f"{model.replace('/', '-')}__{problem.group}__{_combo_key(combo)}.json"
    tpath.write_text(json.dumps({
        "task": problem.group, "model": model, "combo": combo,
        "perturbation": atom or "clean", "question": question,
        "gold": problem.answer, "prediction": pred_text,
        "extracted": extract_answer(pred_text) if pred_text else None,
        "status": status, "passed": passed, "error": error,
    }, indent=2), encoding="utf-8")

    return {"task": problem.group, "title": problem.id, "model": model,
            "phase": "clean" if not combo else "search", "combo": combo,
            "note": _NOTES.get(atom, atom) if atom else "clean question",
            "passed": passed, "status": status, "steps": 1, "seconds": elapsed,
            "error": error, "transcript": str(tpath)}


def _load_progress(results_path: Path | None, model: str, resume: bool):
    current, done = [], {}
    if not (results_path and Path(results_path).exists()):
        return current, done
    try:
        previous = json.loads(Path(results_path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return current, done
    in_scope_ok = {}
    for r in previous:
        if r.get("model") != model:
            current.append(r)
            continue
        if resume and r.get("status", "ok") == "ok":
            in_scope_ok[(r["task"], _combo_key(r.get("combo")))] = r
    for (task_id, ckey), r in in_scope_ok.items():
        current.append(r)
        done.setdefault(task_id, {})[ckey] = r
    return current, done


def run_math_suite(model: str, problems: list[MathProblem], out_dir: Path,
                   results_path: Path | None = None, resume: bool = True) -> list[dict]:
    """Evaluate `model` on `problems` with a single-perturbation worst-case sweep.

    Checkpoints after every run (crash-safe); re-running the same command resumes.
    """
    provided = any(p.perturbation != "clean" for p in problems)
    current, done = _load_progress(results_path, model, resume)

    def checkpoint(rec):
        current.append(rec)
        done.setdefault(rec["task"], {})[_combo_key(rec.get("combo"))] = rec
        if results_path:
            _atomic_write_json(results_path, current)

    if results_path:
        _atomic_write_json(results_path, current)

    if provided:
        _run_provided(model, problems, out_dir, done, checkpoint)
    else:
        _run_synth(model, problems, out_dir, done, checkpoint)
    return current


def _run_synth(model, problems, out_dir, done, checkpoint):
    for p in problems:
        pd = done.get(p.group, {})
        clean = pd.get("clean")
        if clean is None:
            print(f"  [{model}] {p.id} :: clean ...", end="", flush=True)
            clean = _run_one(p, model, "", out_dir)
            checkpoint(clean)
            label = "PASS" if clean["passed"] else ("ERROR" if clean["status"] == "error" else "fail")
            print(f" {label}")
        else:
            print(f"  [{model}] {p.id} :: clean ... (resumed)")
        if clean["status"] == "error" or not clean["passed"]:
            continue
        for atom in MATH_ATOMS:
            if _combo_key([atom]) in pd:
                continue
            print(f"    attack {p.id} [{model}] :: {atom} ...", end="", flush=True)
            r = _run_one(p, model, atom, out_dir)
            checkpoint(r)
            out = "ERROR" if r["status"] == "error" else ("BROKE" if not r["passed"] else "SURVIVED")
            print(f" {out}")
    return list(MATH_ATOMS)


def _run_provided(model, problems, out_dir, done, checkpoint):
    by_group = {}
    for p in problems:
        by_group.setdefault(p.group, {"clean": None, "variants": []})
        if p.perturbation == "clean":
            by_group[p.group]["clean"] = p
        else:
            by_group[p.group]["variants"].append(p)
    atoms = sorted({p.perturbation for p in problems if p.perturbation != "clean"})

    for group, bundle in by_group.items():
        seed = bundle["clean"]
        pd = done.get(group, {})
        if seed is None:
            continue  # no clean baseline -> cannot assess robustness
        clean = pd.get("clean")
        if clean is None:
            print(f"  [{model}] {seed.id} :: clean ...", end="", flush=True)
            clean = _run_one(seed, model, "", out_dir)
            checkpoint(clean)
            print(f" {'PASS' if clean['passed'] else 'fail'}")
        if clean["status"] == "error" or not clean["passed"]:
            continue
        for variant in bundle["variants"]:
            atom = variant.perturbation
            if _combo_key([atom]) in pd:
                continue
            r = _run_one(variant, model, atom, out_dir, apply_perturbation=False)
            r["note"] = f"provided variant: {atom}"
            checkpoint(r)
            out = "ERROR" if r["status"] == "error" else ("BROKE" if not r["passed"] else "SURVIVED")
            print(f"    attack {seed.id} [{model}] :: {atom} ... {out}")
    return atoms
