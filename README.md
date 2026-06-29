# agentic-coding-evals

An **adversarial-robustness eval for coding agents**. It measures not just whether a
model can solve a coding task (capability, `pass@1`) but whether it stays correct when
the task is rewritten in ways that *don't change the right answer* — the coding analog
of an **adversarial example**.

The lens is deliberately *worst-case* rather than average-case: label-preserving
perturbations, a search for the variant that breaks the agent, and attack
transferability across models — applied to frontier coding agents accessed the way
they're actually used (API + tools).

## The idea in one minute

- **Eval** — a repeatable, scored test of model behavior (unit tests, but for a model).
- **Agentic eval** — the model runs a *loop with tools* (read files, write code, run
  code) until it declares done; we then run hidden tests to score it. This mirrors how
  Claude Code / Cursor actually work.
- **`pass@1`** — the headline capability number (% solved on the first attempt).
- **The twist (the differentiator):** every task is also attacked with
  **semantics-preserving perturbations** — the correct fix is unchanged, so a robust
  agent should be *invariant*. We search for the worst case and report **`robust
  pass@1`**: a task counts only if it survived *every* perturbation we tried.

## Why this is an adversarial-robustness eval (the mapping)

| Adversarial robustness (vision) | This project (coding agents) |
|---|---|
| `x_adv` is ε-close to `x`, **same true label** | task variant is semantics-preserving, **same correct fix** |
| FGSM = one fixed perturbation | a single perturbation atom |
| **PGD = iterative search for the worst case** | **search/stack perturbations to find what breaks the agent** |
| attack success rate | % of clean-solved tasks flipped to FAIL |
| transfer across models | does an attack on model A also break model B? |
| causal ablation of the mechanism | per-perturbation failure attribution |

## Perturbation atoms (all label-preserving)

Prompt-level (repo untouched):
- `vague` — instructions cut to a one-line under-specified ask (goal inference)
- `paraphrase` — faithful reword of the full instruction (a *control*: should NOT break)
- `verbose` — the real ask buried in irrelevant-but-true context (signal vs noise)

Repo-level (instruction untouched, behavior preserved):
- `misleading_comment` — a false "already correct, do not change" banner (read code, not prose)
- `distractor_files` — plausible look-alike files added (focus / edit the right file)
- `dead_code` — unused imports/helpers prepended (ignore noise)
- `reformat` — cosmetic reformatting (brittleness to surface form)

The worst-case search sweeps every atom, then escalates to size-2 combinations only if
the model survived all singles (FGSM → PGD).

## Dashboard — no code required

Prefer point-and-click over the CLI? Launch the local web dashboard:

```bash
cd agentic-coding-evals
python -m agenteval dashboard          # opens http://127.0.0.1:8765 in your browser
```

From the browser you can pick a model, select which tasks to run, tune the
worst-case search (strategy, budget, stacking depth, agent steps) and grader
(local or Docker), launch a run, watch live progress stream in, and read the
rendered scorecard — capability vs. worst-case robustness, failure-class
attribution, the transfer matrix, and per-task detail. Click any task to inspect
its prompt, starting code, reference solution, and hidden grader.

It's pure standard library (no web framework, no build step) and just shells out
to the same `run` command, so the dashboard and CLI always agree. For real models,
put an API key in `.env` and it's picked up automatically.

## Quickstart — full demo, no API key needed

Three keyless backends let you see the *entire* attack + transfer pipeline work:

```bash
cd agentic-coding-evals
python -m agenteval run --model reference   # oracle: unbreakable, 100% robust ceiling
python -m agenteval run --model brittle-a   # demo agent with one set of weaknesses
python -m agenteval run --model brittle-b   # demo agent with a DIFFERENT set
python -m agenteval report                  # scorecard incl. the transfer table
```

`brittle-a` and `brittle-b` share one weakness (`vague`) and differ on the rest, so the
transfer table shows **partial** transfer — exactly the phenomenon the metric is meant
to surface.

## Evaluate a real frontier model

```bash
pip install anthropic                 # or: pip install openai
setx ANTHROPIC_API_KEY "sk-..."       # open a new shell afterwards
python -m agenteval run --model claude-3-5-sonnet-latest
python -m agenteval report
```

Outputs:
- `results/report.md` — clean pass@1, robust pass@1, attack success rate, failure-class
  attribution, and the cross-model transfer table
- `results/results.json` — raw per-(task, perturbation) outcomes (models accumulate here)
- `results/transcripts/` — full step-by-step agent logs (where "model taste" lives)

For a step-by-step, full-suite walkthrough (dashboard and CLI, reading results,
Docker grading, cost/time), see **[RUNNING.md](RUNNING.md)**.

## Run controls

```
--search greedy|random|none   worst-case search strategy (default: greedy)
--budget N                    max perturbation evaluations per task (default: 24)
--max-size N                  max atoms stacked when escalating (default: 2)
--tasks id1,id2               run a subset of tasks
--max-steps N                 agent step budget per run (default: 14)
--grader local|docker         grade in-process or in an isolated container (default: local)
```

## How it works

```
tasks/<id>/
  task.json     id, title, prompt, prompt_vague, prompt_paraphrase
  workspace/    starting buggy/incomplete code (copied to a temp dir per run)
  solution/     reference fix (used by `reference` agent + as oracle)
  check.py      functional grader (SWE-bench style): FAIL_TO_PASS + PASS_TO_PASS
```

### The task suite (12 tasks)
Small, self-contained versions of everyday engineering work — each is a single
standard-library Python module with a crisp, testable spec, so grading is unambiguous.

**Bug-fix** (localize and fix a planted defect, like a GitHub issue): off-by-one in
pagination offsets · version comparison ordering numbers as text (`1.10` vs `1.9`) ·
CSV parser breaking on quoted commas · an LRU cache that evicts recently-used entries ·
a token-bucket limiter that overfills after idle time · date arithmetic ignoring leap
years · binary search returning a non-leftmost match.

**Implement-from-spec** (build a function to a ticket): `slugify` · recursive `deep_merge`
for dicts · Luhn checksum validation · URL query-string parsing · email redaction.

For each task: run it clean (is it solvable at all?), then — for clean-solved tasks —
run the worst-case perturbation search. Each variant copies `workspace/` to a temp dir,
applies the perturbation, runs the agent loop (`list_files`, `read_file`, `write_file`,
`run_python`, `submit`), and grades with `check.py`. The grader is never shown to the agent.

### Grading is functional, like SWE-bench (not string matching)
A task is **resolved** iff the agent's edits make the hidden test suite pass — exactly
the SWE-bench contract:
- **FAIL_TO_PASS** — tests that fail on the buggy workspace and must pass after the fix
  (they prove the bug was actually fixed / the feature implemented).
- **PASS_TO_PASS** — tests that already pass and must stay passing (regression guard).

The tests *are* the spec; we never grade the model's prose. This is why an
under-specified (`vague`) run can still legitimately fail: the fixed test suite defines
correctness regardless of how the prompt is phrased.

With `--grader docker`, each grade runs inside a throwaway `python:3.11-slim` container
(`--network none`, with memory/CPU limits), the way SWE-bench isolates every instance, so
the result can't be polluted by the host and model-written code can't touch the network.
`--grader local` (default) runs the grader in a subprocess with a timeout — fine for these
trusted tasks and dependency-free to run.

### Infrastructure errors are excluded, never counted as attacks
A run that raises a transient API error (connection drop, rate limit, timeout, 5xx) is
retried with backoff; if it still fails it is recorded with `status="error"` and
**excluded from every metric** — it is never counted as a successful attack. The
scorecard's "excluded (infra)" column reports how many were dropped. (Real eval
harnesses, SWE-bench included, must separate infra flakiness from genuine failures.)

## Extending it

- **Add a task:** create `tasks/<id>/` with the four pieces above.
- **Add a perturbation:** add an atom in `agenteval/perturb.py` and list it in `ATOMS`.
  Keep it *label-preserving* (the correct fix must not change).
- **Add a model backend:** extend `agenteval/agent.py` (`run_llm_agent`).
- **Toward real SWE-bench:** swap synthetic tasks for git-checkout repos + a test command;
  the runner/grader contract stays the same.

## Related work

This is a compact, from-scratch implementation of an **established and active research
direction**, not a novel benchmark — robustness of code models to semantics-preserving
changes has been studied directly:

- **ReCode** (Wang et al., ACL 2023) — the closest predecessor: 30+ semantics-preserving
  perturbations (docstrings, names, syntax, formatting) over HumanEval/MBPP, graded by
  execution, with a **worst-case "Robust Pass@k"**. The prompt/repo atoms and the
  worst-case framing here are a small, agentic subset of that idea.
- **ReliabilityBench** (2026) — evaluates agents along the same three axes used here:
  repeated-run consistency, **robustness to task perturbations**, and **fault tolerance
  under infrastructure failures** (timeouts, rate limits) — the latter being exactly the
  infra-error exclusion this harness implements.
- **EvaLooop** (2025) — perturbation robustness of coding LLMs; reports the same
  "which model is more robust depends on the perturbation" effect that motivates the
  per-perturbation attribution and transfer table here.
- **SWE-ABS / SWE-bench-A2A** (2026) — show that weak test suites overstate SWE-bench
  scores and apply mutation / semantics-preserving perturbations and cross-provider
  robustness checks; motivation for the functional FAIL_TO_PASS/PASS_TO_PASS grading.
- **SWE-bench** (Jimenez et al., 2023) — the execution-based, container-isolated grading
  contract this harness mirrors.

The contribution of this repo is **pedagogical and infrastructural**: a small, readable,
end-to-end agentic harness (tool-use loop + worst-case search + transfer analysis +
infra-aware functional grading) you can run and extend in minutes — not a new dataset or
a state-of-the-art claim.

## Honest limitations

- Twelve small, self-contained tasks: enough to demonstrate the method and read
  transcripts, not to rank models with statistical confidence. Scale task count (and add
  real git-checkout repos) for production-grade signal.
- `pass@1` only (no pass@k yet). The search is a small combinatorial sweep, not a learned
  attacker.
- Perturbations operate at the input (task) level, which is what API-only models expose.
  Representation-level attacks would need model internals; a latent-space probe on an
  open-weight coding model is a natural future extension, not implemented here.
- Container grading (`--grader docker`) requires a running Docker daemon; the default
  local grader keeps the project dependency-free to run.

## License

MIT — see [LICENSE](LICENSE).
