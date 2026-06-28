"""Renders results.json into an adversarial-robustness scorecard.

Metrics (named to mirror adversarial-robustness work):
  clean pass@1      accuracy with no perturbation
  robust pass@1     worst-case accuracy: a task counts as solved only if it
                    survived EVERY semantics-preserving perturbation we tried
  ASR               attack success rate = of the tasks the model solved clean,
                    the fraction where some perturbation flipped pass -> fail
  failure class     which perturbation atom caused breaks, and how often
  transfer          do attacks found against model A also break model B?
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .perturb import ATOMS


def _index(results: list[dict]):
    models = sorted({r["model"] for r in results})
    clean = {}                              # (model, task) -> passed
    tasks_of = defaultdict(set)             # model -> {task}
    single_fail = defaultdict(set)          # (model, task) -> {atom that broke alone}
    any_fail = defaultdict(set)             # (model, task) -> {combo_key that broke}
    titles = {}

    for r in results:
        m, t = r["model"], r["task"]
        titles[t] = r.get("title", t)
        if r.get("phase") == "clean" or not r.get("combo"):
            clean[(m, t)] = r["passed"]
            tasks_of[m].add(t)
        else:
            combo = r["combo"]
            if not r["passed"]:
                any_fail[(m, t)].add("+".join(combo))
                if len(combo) == 1:
                    single_fail[(m, t)].add(combo[0])
    return models, clean, tasks_of, single_fail, any_fail, titles


def build_report(results: list[dict]) -> str:
    models, clean, tasks_of, single_fail, any_fail, titles = _index(results)

    L = ["# Adversarial Robustness Scorecard - Coding Agents", "",
         "Each task is perturbed with **semantics-preserving** transformations "
         "(the correct fix never changes). A robust agent should be invariant to "
         "them; where it is not, we have an attack. `robust pass@1` is the "
         "**worst-case** accuracy: a task counts only if it survived *every* "
         "perturbation tried.", ""]

    # ---- headline table -----------------------------------------------------
    L += ["| Model | clean pass@1 | robust pass@1 | attack success rate | solved clean |",
          "|---|---|---|---|---|"]
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
                 f"{asr:.0f}% | {len(solved)}/{n} |")

    # ---- failure-class attribution -----------------------------------------
    L += ["", "## Failure classes (which perturbation caused breaks)", "",
          "Counts of *clean-solved* tasks broken by each single perturbation, per model.", "",
          "| Perturbation | " + " | ".join(f"`{m}`" for m in models) + " |",
          "|" + "---|" * (len(models) + 1)]
    for atom in ATOMS:
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


def render(results_path: Path, out_path: Path) -> None:
    results = json.loads(Path(results_path).read_text(encoding="utf-8"))
    Path(out_path).write_text(build_report(results), encoding="utf-8")
