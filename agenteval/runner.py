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
import os
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

# Image used by the containerized grader. Plain CPython, no third-party deps:
# every task and grader is pure standard library by design.
DOCKER_IMAGE = "python:3.11-slim"


def _combo_key(combo) -> str:
    """Stable identifier for a (task,variant): 'clean' or 'atom[+atom...]'."""
    return "+".join(combo) if combo else "clean"


def _atomic_write_json(path: Path, data) -> None:
    """Write JSON to `path` crash-safely (temp file + atomic replace).

    Used to checkpoint progress after every run, so a connection drop or a
    killed process leaves a complete, loadable results file to resume from.
    """
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


def _grade_docker(ws: Path) -> tuple[bool, str]:
    """Run the grader inside a throwaway, network-less container.

    This mirrors how SWE-bench grades each instance in an isolated image so the
    result cannot be polluted by the host environment, and arbitrary model-written
    code in the workspace cannot touch the network or the rest of the machine.
    The grader file is already copied into `ws`, which is bind-mounted read-write.
    """
    host = str(ws.resolve()).replace("\\", "/")  # Docker Desktop accepts C:/... on Windows
    cmd = ["docker", "run", "--rm",
           "--network", "none", "--memory", "512m", "--cpus", "1",
           "-v", f"{host}:/work", "-w", "/work",
           DOCKER_IMAGE, "python", "_grader_check.py"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        return r.returncode == 0, (r.stdout + r.stderr)[-1500:]
    except subprocess.TimeoutExpired:
        return False, "docker grader timed out"
    except FileNotFoundError:
        return False, "docker not found on PATH (use --grader local)"


def require_docker() -> None:
    """Fail fast (before any grading) if --grader docker can't reach a daemon.

    Without this, a stopped Docker daemon would make every grade return False and
    masquerade as the model failing every task. An unreachable grader is an
    infrastructure problem, not a model result, so we refuse to run instead.
    """
    try:
        r = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=20)
    except FileNotFoundError:
        raise SystemExit("docker not found on PATH. Install Docker, or use --grader local.")
    except subprocess.TimeoutExpired:
        raise SystemExit("`docker info` timed out. Is the Docker daemon healthy? "
                         "Start Docker Desktop, or use --grader local.")
    if r.returncode != 0:
        raise SystemExit("Cannot reach the Docker daemon (is Docker Desktop running?). "
                         "Start it, or use --grader local.")


def _grade(task: Task, ws: Path, grader: str = "local") -> tuple[bool, str]:
    grader_file = ws / "_grader_check.py"
    shutil.copy2(task.check_path, grader_file)
    try:
        if grader == "docker":
            return _grade_docker(ws)
        r = subprocess.run([sys.executable, "_grader_check.py"], cwd=ws,
                           capture_output=True, text=True, timeout=30)
        return r.returncode == 0, (r.stdout + r.stderr)[-1500:]
    except subprocess.TimeoutExpired:
        return False, "grader timed out"
    finally:
        grader_file.unlink(missing_ok=True)


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
                max_steps: int = 14, max_retries: int = 3,
                grader: str = "local") -> dict:
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

    passed, grader_out = (None, "") if status == "error" else _grade(task, ws, grader)
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


def _outcome(r: dict) -> str:
    # A break requires a genuine (status ok) run that failed grading.
    # Errored runs are infra noise: neither a break nor a clean survival.
    if r.get("status", "ok") == "error":
        return "errored"
    return "broke" if not r["passed"] else "survived"


def search_worstcase(task: Task, model: str, out_dir: Path, budget: int,
                     max_size: int, strategy: str, max_steps: int,
                     grader: str = "local", done: dict | None = None,
                     record=None) -> list[dict]:
    """Search semantics-preserving perturbations for ones that break the model.

    Sweeps every single atom (recording each outcome so we can attribute and
    transfer failures), then escalates to size-2 combos only if every single
    atom survived and the budget allows.

    Resumable: `done` maps combo_key -> a previously completed (status="ok")
    record for this (model, task); those variants are skipped and reused.
    `record`, if given, is called with each newly produced record so the caller
    can checkpoint it to disk immediately. `budget` counts only NEW evaluations
    this session, so a resumed run continues rather than re-doing work.
    """
    import random

    done = done or {}
    records: list[dict] = []
    evals = 0

    atoms = list(perturb.ATOMS)
    if strategy == "random":
        random.shuffle(atoms)

    any_single_break = False
    for a in atoms:
        cached = done.get(_combo_key([a]))
        if cached is not None:
            out = _outcome(cached)
            any_single_break = any_single_break or (out == "broke")
            print(f"    attack {task.id} [{model}] :: {a} ... (resumed: {out.upper()})")
            continue
        if evals >= budget:
            break
        print(f"    attack {task.id} [{model}] :: {a} ...", end="", flush=True)
        r = run_variant(task, model, [a], out_dir, max_steps=max_steps, grader=grader)
        records.append(r)
        if record:
            record(r)
        evals += 1
        out = _outcome(r)
        any_single_break = any_single_break or (out == "broke")
        print(f" {out.upper()}")

    if not any_single_break and max_size >= 2:
        combos = list(itertools.combinations(perturb.ATOMS, 2))
        if strategy == "random":
            random.shuffle(combos)
        for c in combos:
            cached = done.get(_combo_key(c))
            if cached is not None:
                out = _outcome(cached)
                print(f"    attack {task.id} [{model}] :: {'+'.join(c)} ... "
                      f"(resumed: {out.upper()})")
                if out == "broke":
                    break
                continue
            if evals >= budget:
                break
            print(f"    attack {task.id} [{model}] :: {'+'.join(c)} ...",
                  end="", flush=True)
            r = run_variant(task, model, list(c), out_dir, max_steps=max_steps, grader=grader)
            records.append(r)
            if record:
                record(r)
            evals += 1
            out = _outcome(r)
            print(f" {out.upper()}")
            if out == "broke":
                break

    return records


def _load_progress(results_path: Path | None, model: str,
                   only: list[str] | None, resume: bool):
    """Split any existing results.json into (rows to preserve, resume index).

    Returns (current_rows, done) where:
      current_rows  every row we keep up front -- all OTHER models' rows, plus
                    this model's already-completed (status="ok") rows when
                    resuming. This is the live list we checkpoint to disk.
      done          {task_id: {combo_key: record}} of this model's reusable
                    runs, so the suite can skip work it already did.

    Rows for THIS model that errored (status="error") are dropped so a resumed
    run RETRIES them -- a connection drop should not be remembered as a result.
    With resume=False, all of this model's in-scope rows are dropped (fresh run).
    """
    current: list[dict] = []
    done: dict[str, dict] = {}
    if not (results_path and Path(results_path).exists()):
        return current, done

    try:
        previous = json.loads(Path(results_path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return current, done

    in_scope_ok: dict[tuple, dict] = {}
    for r in previous:
        in_scope = r.get("model") == model and (not only or r.get("task") in only)
        if not in_scope:
            current.append(r)            # other models / tasks: always preserve
            continue
        if resume and r.get("status", "ok") == "ok":
            # de-dupe on (task, combo); a later row wins if any duplicates exist
            in_scope_ok[(r["task"], _combo_key(r.get("combo")))] = r

    for (task_id, ckey), r in in_scope_ok.items():
        current.append(r)
        done.setdefault(task_id, {})[ckey] = r
    return current, done


def run_suite(suite_dir: Path, model: str, out_dir: Path,
              only: list[str] | None = None, max_steps: int = 14,
              search: str = "greedy", budget: int = 24, max_size: int = 2,
              grader: str = "local", results_path: Path | None = None,
              resume: bool = True) -> list[dict]:
    """Run the eval, checkpointing to `results_path` after every single run.

    Because progress is flushed to disk crash-safely as it happens, an
    interrupted run (lost connection, killed process, machine sleep) can be
    continued simply by invoking the same command again: completed variants are
    reloaded and skipped, and any infra-errored variants are retried.
    """
    if grader == "docker":
        require_docker()

    tasks = discover_tasks(suite_dir, only=only)
    if not tasks:
        raise SystemExit(f"No tasks found in {suite_dir}")

    current, done = _load_progress(results_path, model, only, resume)

    def _checkpoint(rec: dict) -> None:
        current.append(rec)
        done.setdefault(rec["task"], {})[_combo_key(rec.get("combo"))] = rec
        if results_path:
            _atomic_write_json(results_path, current)

    resumed = sum(len(v) for v in done.values())
    if resumed:
        print(f"  (resuming: {resumed} completed run(s) reloaded; "
              "they will be skipped, infra errors retried)")
    if results_path:
        _atomic_write_json(results_path, current)  # persist the pruned state now

    for task in tasks:
        task_done = done.get(task.id, {})
        clean = task_done.get("clean")
        if clean is not None:
            label = "PASS" if clean["passed"] else "fail"
            print(f"  [{model}] {task.id} :: clean ... (resumed: {label})")
        else:
            print(f"  [{model}] {task.id} :: clean ...", end="", flush=True)
            clean = run_variant(task, model, [], out_dir, max_steps=max_steps, grader=grader)
            label = ("PASS" if clean["passed"] else
                     "ERROR" if clean["status"] == "error" else "fail")
            print(f" {label} ({clean['steps']} steps, {clean['seconds']}s)")
            _checkpoint(clean)

        if clean["status"] == "error":
            print(f"    (skipping attacks: clean run errored for {task.id} -- "
                  "cannot assess robustness)")
            continue
        if not clean["passed"]:
            print(f"    (skipping attacks: model cannot solve {task.id} clean)")
            continue
        if search == "none":
            continue
        search_worstcase(task, model, out_dir, budget=budget, max_size=max_size,
                         strategy=search, max_steps=max_steps, grader=grader,
                         done=task_done, record=_checkpoint)
    return current
