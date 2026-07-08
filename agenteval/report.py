"""Renders results.json into an adversarial-robustness scorecard.

Grading is **functional** (SWE-bench style): a task is "resolved" iff the agent's
edits make the task's hidden test suite pass (FAIL_TO_PASS go green, PASS_TO_PASS
stay green). We never string-match the model's prose; the tests are the spec.

Runs that errored due to infrastructure (API connection / rate-limit / timeout)
have status="error" and are EXCLUDED from every metric below -- they are never
counted as a successful attack. The coverage line reports how many were excluded.

Metrics:
  clean pass@1      resolved rate with no perturbation
  robust pass@1     worst-case: a task counts only if it stayed resolved under
                    EVERY semantics-preserving perturbation actually tested
  ASR               attack success rate = of tasks solved clean, the fraction
                    where some perturbation flipped resolved -> unresolved
  failure class     which perturbation atom caused breaks, and how often
  transfer          do attacks found against model A also break model B?
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .perturb import ATOMS


def _ok(r: dict) -> bool:
    # Old rows may predate the status field; treat missing status as a real run.
    return r.get("status", "ok") == "ok"


def _index(results: list[dict]):
    models = sorted({r["model"] for r in results})
    clean = {}                              # (model, task) -> passed (ok runs only)
    tasks_of = defaultdict(set)             # model -> {task} (assessable: clean ran ok)
    single_fail = defaultdict(set)          # (model, task) -> {atom that broke alone}
    any_fail = defaultdict(set)             # (model, task) -> {combo_key that broke}
    errors = defaultdict(int)              # model -> count of excluded errored runs
    titles = {}

    for r in results:
        m, t = r["model"], r["task"]
        titles[t] = r.get("title", t)
        if not _ok(r):
            errors[m] += 1
            continue
        if r.get("phase") == "clean" or not r.get("combo"):
            clean[(m, t)] = r["passed"]
            tasks_of[m].add(t)
        else:
            combo = r["combo"]
            if not r["passed"]:
                any_fail[(m, t)].add("+".join(combo))
                if len(combo) == 1:
                    single_fail[(m, t)].add(combo[0])
    return models, clean, tasks_of, single_fail, any_fail, errors, titles


def build_report(results: list[dict], atoms: list[str] | None = None,
                 title: str = "Coding Agents", intro: str | None = None) -> str:
    atoms = list(atoms) if atoms is not None else list(ATOMS)
    models, clean, tasks_of, single_fail, any_fail, errors, titles = _index(results)

    if intro is None:
        intro = ("Grading is **functional / SWE-bench style**: a task is *resolved* iff the "
                 "agent's edits make the hidden test suite pass. Each task is then attacked "
                 "with **semantics-preserving** perturbations (the correct fix never changes); "
                 "a robust agent should stay resolved. `robust pass@1` is the **worst-case**: "
                 "a task counts only if it survived every perturbation tested. Infrastructure "
                 "errors are excluded, never counted as attacks.")
    L = [f"# Adversarial Robustness Scorecard - {title}", "", intro, ""]

    # ---- headline table -----------------------------------------------------
    L += ["| Model | clean pass@1 | robust pass@1 | attack success rate | solved clean | excluded (infra) |",
          "|---|---|---|---|---|---|"]
    for m in models:
        tasks = sorted(tasks_of[m])
        n = len(tasks)
        solved = [t for t in tasks if clean.get((m, t))]
        broken = [t for t in solved if any_fail.get((m, t))]
        survived = [t for t in solved if not any_fail.get((m, t))]
        clean_rate = 100 * len(solved) / n if n else 0
        robust_rate = 100 * len(survived) / n if n else 0
        asr = 100 * len(broken) / len(solved) if solved else 0
        L.append(f"| `{m}` | {clean_rate:.0f}% | {robust_rate:.0f}% | "
                 f"{asr:.0f}% | {len(solved)}/{n} | {errors.get(m, 0)} |")

    # ---- failure-class attribution -----------------------------------------
    L += ["", "## Failure classes (which perturbation caused breaks)", "",
          "Counts of *clean-solved* tasks broken by each single perturbation, per model.", "",
          "| Perturbation | " + " | ".join(f"`{m}`" for m in models) + " |",
          "|" + "---|" * (len(models) + 1)]
    for atom in atoms:
        cells = []
        for m in models:
            solved = [t for t in tasks_of[m] if clean.get((m, t))]
            c = sum(1 for t in solved if atom in single_fail.get((m, t), set()))
            cells.append(str(c) if c else "-")
        L.append(f"| {atom} | " + " | ".join(cells) + " |")

    # ---- transfer table -----------------------------------------------------
    attack_models = [m for m in models
                     if any(single_fail.get((m, t)) for t in tasks_of[m])]
    if len(attack_models) >= 2:
        L += ["", "## Attack transfer (source -> target)", "",
              "Of the single-perturbation attacks that break the **source** model "
              "(on tasks both models solve clean), what fraction also break the "
              "**target**? High = shared blind spots; low = model-specific.", "",
              "| source \\\\ target | " + " | ".join(f"`{m}`" for m in attack_models) + " |",
              "|" + "---|" * (len(attack_models) + 1)]
        for s in attack_models:
            row = [f"| `{s}` "]
            for t_m in attack_models:
                if s == t_m:
                    row.append("| - ")
                    continue
                pairs = hits = 0
                shared = [t for t in tasks_of[s]
                          if clean.get((s, t)) and clean.get((t_m, t))]
                for t in shared:
                    for atom in single_fail.get((s, t), set()):
                        pairs += 1
                        if atom in single_fail.get((t_m, t), set()):
                            hits += 1
                rate = f"{100 * hits / pairs:.0f}% ({hits}/{pairs})" if pairs else "n/a"
                row.append(f"| {rate} ")
            L.append("".join(row) + "|")

    # ---- per-task detail ----------------------------------------------------
    L += ["", "## Per-task detail", "",
          "| Task | Model | clean | broken by (single-perturbation attacks) |",
          "|---|---|---|---|"]
    for m in models:
        for t in sorted(tasks_of[m]):
            cln = "PASS" if clean.get((m, t)) else "**fail**"
            breakers = ", ".join(sorted(single_fail.get((m, t), set()))) or "-"
            L.append(f"| {t} | `{m}` | {cln} | {breakers} |")

    L += ["", "## Model-taste notes (fill in from transcripts/)", "",
          "_Open the per-run transcripts and record concrete failure modes, e.g._",
          "- _Under `vague`, the agent edited the wrong file instead of inspecting first._",
          "- _Under `misleading_comment`, it trusted the banner and submitted with no fix._",
          "- _Attacks via `vague` transferred across models; `distractor_files` did not._", ""]
    return "\n".join(L)


def summarize(results: list[dict], atoms: list[str] | None = None) -> dict:
    """Structured version of the scorecard, for programmatic consumers (the
    dashboard). Same numbers as build_report(), as JSON-friendly dicts."""
    atoms = list(atoms) if atoms is not None else list(ATOMS)
    models, clean, tasks_of, single_fail, any_fail, errors, titles = _index(results)

    model_rows = []
    for m in models:
        tasks = sorted(tasks_of[m])
        n = len(tasks)
        solved = [t for t in tasks if clean.get((m, t))]
        broken = [t for t in solved if any_fail.get((m, t))]
        survived = [t for t in solved if not any_fail.get((m, t))]
        model_rows.append({
            "model": m,
            "clean_pass": round(100 * len(solved) / n, 1) if n else 0.0,
            "robust_pass": round(100 * len(survived) / n, 1) if n else 0.0,
            "asr": round(100 * len(broken) / len(solved), 1) if solved else 0.0,
            "solved": len(solved), "n": n, "errors": errors.get(m, 0),
        })

    failure_classes = []
    for atom in atoms:
        counts = {}
        for m in models:
            solved = [t for t in tasks_of[m] if clean.get((m, t))]
            counts[m] = sum(1 for t in solved if atom in single_fail.get((m, t), set()))
        failure_classes.append({"atom": atom, "counts": counts})

    attack_models = [m for m in models
                     if any(single_fail.get((m, t)) for t in tasks_of[m])]
    matrix = {}
    for s in attack_models:
        matrix[s] = {}
        for t_m in attack_models:
            if s == t_m:
                matrix[s][t_m] = None
                continue
            pairs = hits = 0
            shared = [t for t in tasks_of[s]
                      if clean.get((s, t)) and clean.get((t_m, t))]
            for t in shared:
                for atom in single_fail.get((s, t), set()):
                    pairs += 1
                    if atom in single_fail.get((t_m, t), set()):
                        hits += 1
            matrix[s][t_m] = {"hits": hits, "pairs": pairs,
                              "rate": round(100 * hits / pairs, 1) if pairs else None}

    all_tasks = sorted({t for m in models for t in tasks_of[m]})
    per_task = []
    for t in all_tasks:
        row = {"task": t, "title": titles.get(t, t), "models": {}}
        for m in models:
            if t in tasks_of[m]:
                row["models"][m] = {
                    "clean": bool(clean.get((m, t))),
                    "broken_by": sorted(single_fail.get((m, t), set())),
                }
        per_task.append(row)

    return {
        "models": model_rows,
        "failure_classes": failure_classes,
        "transfer": {"models": attack_models, "matrix": matrix},
        "per_task": per_task,
        "atoms": list(atoms),
    }


def render(results_path: Path, out_path: Path, atoms: list[str] | None = None,
           title: str = "Coding Agents", intro: str | None = None) -> None:
    results = json.loads(Path(results_path).read_text(encoding="utf-8"))
    Path(out_path).write_text(
        build_report(results, atoms=atoms, title=title, intro=intro), encoding="utf-8")
