"""Runs the adversarial-robustness eval for a model.

For each task we:
  1. run the CLEAN task (no perturbation) -> establishes whether the model can
     solve it at all. Only clean-passing tasks are "attackable".
  2. run a worst-case SEARCH over semantics-preserving perturbations (perturb.py):
     sweep every single atom; if the model survives all of them and the budget
     allows, escalate to size-2 combinations. This is the FGSM->PGD analogy:
     instead of one fixed perturbation we search for the worst case.

A task is "broken" if any perturbed variant flips a clean PASS into a FAIL.
Every (task, variant) outcome is recorded so report.py can compute attack
success rate, per-perturbation failure attribution, and cross-model transfer.

Backends:
  reference   oracle; copies solution/ (unbreakable -- validates the plumbing)
  brittle-a   keyless demo agent with a fixed set of weaknesses
  brittle-b   keyless demo agent with a *different* set of weaknesses
              (so the transfer table shows partial, not total, transfer)
  claude-* / gpt-*   real LLM tool-use agents (need an API key)
"""
from __future__ import annotations

import itertools
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import agent, perturb
from .tasks import Task, discover_tasks

# Keyless demo agents: which perturbation atoms deterministically break them.
# brittle-a and brittle-b share `vague` (transfers) but differ otherwise
# (those attacks do NOT transfer) -- a clean demo of the transfer analysis.
BRITTLE_WEAKNESSES = {
    "brittle-a": {"vague", "distractor_files"},
    "brittle-b": {"vague", "misleading_comment"},
}


def _grade(task: Task, ws: Path) -> tuple[bool, str]:
    grader = ws / "_grader_check.py"
    shutil.copy2(task.check_path, grader)
    try:
        r = subprocess.run([sys.executable, "_grader_check.py"], cwd=ws,
                           capture_output=True, text=True, timeout=30)
        return r.returncode == 0, (r.stdout + r.stderr)[-1500:]
    except subprocess.TimeoutExpired:
        return False, "grader timed out"
    finally:
        grader.unlink(missing_ok=True)


def _run_brittle(model: str, combo: list[str], task: Task, ws: Path) -> dict:
    """Deterministic demo agent: solves the task UNLESS a triggering atom is in
    the combo, in which case it leaves the repo unfixed (and fails grading)."""
    weak = BRITTLE_WEAKNESSES.get(model, set())
    triggered = sorted(weak.intersection(combo))
    if triggered:
        return {"steps": 1,
                "transcript": [{"tool": "give_up", "triggered_by": triggered}]}
    return agent.run_reference(task.solution_dir, ws)


def run_variant(task: Task, model: str, combo: list[str], out_dir: Path,
                max_steps: int = 14, max_retries: int = 3) -> dict:
    """Apply `combo`, run the agent, grade, persist a transcript, return a record.

    Distinguishes two kinds of non-pass, the way a real eval harness must:
      status="ok"     the agent loop completed; `passed` is the genuine result
                      of functional grading (this is a real model outcome).
      status="error"  the agent run raised (API connection / rate-limit / timeout
                      / config). Retried up to `max_retries` with backoff; if it
                      still fails it is recorded but EXCLUDED from the scorecard
                      and is NEVER counted as a successful attack.
    """
    work = Path(tempfile.mkdtemp(prefix=f"{task.id}_"))
    ws = work / "repo"
    shutil.copytree(task.workspace_dir, ws)

    prompt_body, note = perturb.apply_combo(combo, task, ws, task.prompt)
    full_prompt = (f"{prompt_body}\n\nThe repository is your working directory. "
                   "Fix it so the tests pass.")

    t0 = time.time()
    error = ""
    result = {"steps": 0, "transcript": []}
    status = "ok"
    for attempt in range(1, max_retries + 2):
        # fresh workspace each attempt (a partial run may have edited it)
        if attempt > 1:
            shutil.rmtree(ws, ignore_errors=True)
            shutil.copytree(task.workspace_dir, ws)
            perturb.apply_combo(combo, task, ws, task.prompt)
        try:
            if model == "reference":
                result = agent.run_reference(task.solution_dir, ws)
            elif model in BRITTLE_WEAKNESSES:
                result = _run_brittle(model, combo, task, ws)
            else:
                result = agent.run_llm_agent(model, full_prompt, ws, max_steps=max_steps)
            status, error = "ok", ""
            break
        except Exception as e:  # noqa: BLE001 - we classify below
            error = f"{type(e).__name__}: {e}"
            result = {"steps": 0, "transcript": [{"fatal": error}]}
            transient = agent.is_transient_error(e)
            if transient and attempt <= max_retries:
                time.sleep(min(2 ** attempt, 20))
                continue
            # any uncaught agent-run exception means no genuine attempt happened
            status = "error"
            break

    passed, grader_out = (None, "") if status == "error" else _grade(task, ws)
    elapsed = round(time.time() - t0, 1)

    combo_key = "+".join(combo) if combo else "clean"
    tdir = out_dir / "transcripts"
    tdir.mkdir(parents=True, exist_ok=True)
    tpath = tdir / f"{model.replace('/', '-')}__{task.id}__{combo_key}.json"
    tpath.write_text(json.dumps(
        {"task": task.id, "model": model, "combo": combo, "note": note,
         "status": status, "passed": passed, "error": error,
         "grader_out": grader_out, "transcript": result["transcript"]},
        indent=2), encoding="utf-8")

    shutil.rmtree(work, ignore_errors=True)
    return {"task": task.id, "title": task.title, "model": model,
            "phase": "clean" if not combo else "search",
            "combo": combo, "note": note, "passed": passed,
            "status": status, "steps": result.get("steps", 0), "seconds": elapsed,
            "error": error, "transcript": str(tpath)}


def search_worstcase(task: Task, model: str, out_dir: Path, budget: int,
                     max_size: int, strategy: str, max_steps: int) -> list[dict]:
    """Search semantics-preserving perturbations for ones that break the model.

    Sweeps every single atom (recording each outcome so we can attribute and
    transfer failures), then escalates to size-2 combos only if every single
    atom survived and the budget allows.
    """
    import random

    records: list[dict] = []
    evals = 0

    atoms = list(perturb.ATOMS)
    if strategy == "random":
        random.shuffle(atoms)

    def _outcome(r: dict) -> str:
        # A break requires a genuine (status ok) run that failed grading.
        # Errored runs are infra noise: neither a break nor a clean survival.
        if r["status"] == "error":
            return "errored"
        return "broke" if not r["passed"] else "survived"

    any_single_break = False
    for a in atoms:
        if evals >= budget:
            break
        print(f"    attack {task.id} [{model}] :: {a} ...", end="", flush=True)
        r = run_variant(task, model, [a], out_dir, max_steps=max_steps)
        records.append(r)
        evals += 1
        out = _outcome(r)
        any_single_break = any_single_break or (out == "broke")
        print(f" {out.upper()}")

    if not any_single_break and max_size >= 2:
        combos = list(itertools.combinations(perturb.ATOMS, 2))
        if strategy == "random":
            random.shuffle(combos)
        for c in combos:
            if evals >= budget:
                break
            print(f"    attack {task.id} [{model}] :: {'+'.join(c)} ...",
                  end="", flush=True)
            r = run_variant(task, model, list(c), out_dir, max_steps=max_steps)
            records.append(r)
            evals += 1
            out = _outcome(r)
            print(f" {out.upper()}")
            if out == "broke":
                break

    return records


def run_suite(suite_dir: Path, model: str, out_dir: Path,
              only: list[str] | None = None, max_steps: int = 14,
              search: str = "greedy", budget: int = 24, max_size: int = 2) -> list[dict]:
    tasks = discover_tasks(suite_dir, only=only)
    if not tasks:
        raise SystemExit(f"No tasks found in {suite_dir}")

    results: list[dict] = []
    for task in tasks:
        print(f"  [{model}] {task.id} :: clean ...", end="", flush=True)
        clean = run_variant(task, model, [], out_dir, max_steps=max_steps)
        label = ("PASS" if clean["passed"] else
                 "ERROR" if clean["status"] == "error" else "fail")
        print(f" {label} ({clean['steps']} steps, {clean['seconds']}s)")
        results.append(clean)

        if clean["status"] == "error":
            print(f"    (skipping attacks: clean run errored for {task.id} -- "
                  "cannot assess robustness)")
            continue
        if not clean["passed"]:
            print(f"    (skipping attacks: model cannot solve {task.id} clean)")
            continue
        if search == "none":
            continue
        results.extend(search_worstcase(task, model, out_dir, budget=budget,
                                        max_size=max_size, strategy=search,
                                        max_steps=max_steps))
    return results
