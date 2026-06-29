# Running a real model (full-suite walkthrough)

This guide walks through kicking off a **fresh, full-suite run** against a real
frontier model end to end. The example uses Anthropic's Haiku, but the same steps
work for any `claude-*` or `gpt-*` model.

A "full-suite" run evaluates the model on **all 12 tasks**, and for each task the
harness searches semantics-preserving perturbations (the worst-case attack search)
to measure robustness — not just whether the model can solve the clean task once.

---

## 0. Prerequisites (one time)

1. **Python 3.10+** and the dependencies:

```bash
pip install -r requirements.txt
```

2. **An API key in `.env`.** Copy the example and paste your key in:

```bash
cp .env.example .env
```

Then open `.env` and set:

```
ANTHROPIC_API_KEY=sk-ant-...your key...
```

`.env` is gitignored — it is never committed or pushed. The dashboard and the CLI
both load it automatically.

> Sanity check (optional): `python -m agenteval run --model reference` runs the
> keyless oracle backend over the suite in a few seconds. If that prints a
> scorecard, your install is good.

---

## 1. Start clean (recommended)

If `results/` already contains data from earlier demo runs (e.g. `reference`,
`brittle-a`, `brittle-b`), clear it so the scorecard shows only your real run:

```bash
# from the dashboard: click "clear results"
# or from the shell:
rm -rf results/results.json results/report.md results/transcripts
```

---

## 2A. Kick off the run — Dashboard (no coding)

1. Launch the dashboard:

```bash
python -m agenteval dashboard
```

   Your browser opens at `http://127.0.0.1:8765/`.

2. In the left panel:
   - **Model** → choose `custom API model…` and type `claude-haiku-4-5-20251001`.
     (The note should say "API key detected in .env".)
   - **Search** → `greedy` (worst-case attack search).
   - **Grader** → `local` (or `docker` for isolated grading — see below).
   - **Budget / Stack / Steps** → leave at defaults (24 / 2 / 14).
   - **Tasks** → leave **all 12** checked (this is the "full suite").

3. Click **Run experiment**. Watch the live log: each task runs `clean` first,
   then the attack search (`SURVIVED` / `BROKE` lines). When it finishes, the
   scorecard below populates automatically.

---

## 2B. Kick off the run — Command line

Run the full suite under the greedy worst-case search, then render the scorecard:

```bash
python -u -m agenteval run --model claude-haiku-4-5-20251001 --search greedy
python -m agenteval report
```

Notes:
- Omitting `--tasks` runs **all 12 tasks** (the full suite).
- `python -u` streams progress live instead of buffering it.
- Defaults: `--budget 24 --max-size 2 --max-steps 14 --grader local`.
- To scope a quick test to a couple of tasks first:
  `--tasks implement-slugify,fix-pagination`.

---

## 3. Read the results

After the run, you'll have:

- **`results/report.md`** — the markdown scorecard (headline metrics, failure
  classes, transfer table, per-task detail).
- **`results/results.json`** — the raw per-run records.
- **`results/transcripts/`** — every step the agent took, per task/perturbation,
  for "model taste" inspection.
- **The dashboard** — the same scorecard, rendered interactively.

Key metrics:
- **clean pass@1** — solved the unperturbed task.
- **robust pass@1** — worst-case: a task counts only if it survived *every*
  perturbation tested. The gap between clean and robust is the model's fragility.
- **attack success rate** — fraction of clean-solved tasks that some perturbation
  broke.
- **failure classes** — which perturbations (e.g. `vague`, `misleading_comment`)
  broke the most tasks.
- **infra excl.** — runs dropped because of transient API/infrastructure errors
  (retried first, then excluded from metrics so they never masquerade as model
  failures).

---

## 4. Optional: isolated (Docker) grading

For SWE-bench-style isolation, grade each task inside a throwaway container with no
network and capped resources:

```bash
python -u -m agenteval run --model claude-haiku-4-5-20251001 --search greedy --grader docker
```

Requires Docker Desktop running. The harness preflights the Docker daemon and
fails fast with a clear message if it's unreachable (rather than silently scoring
everything as failed).

---

## 5. Cost & time expectations

- Each task does one clean attempt plus a perturbation search (budget 24). With a
  small fast model like Haiku the full suite typically completes in a handful of
  minutes; larger models take longer.
- Cost scales with the number of model calls (tasks × perturbations × agent steps).
  Lower it for a cheaper smoke test with `--search none` (clean-only) or
  `--budget 6`.

---

## Troubleshooting

- **"No API key found"** in the dashboard → your key isn't in `.env`, or you
  edited a different `.env`. Confirm the file is at the project root next to
  `requirements.txt`.
- **404 / unknown model** → the model id isn't available to your account. List
  what's available, then use the exact id (e.g. `claude-haiku-4-5-20251001`).
- **A run looks stuck** → check the live log; transient API errors are retried
  automatically and reported as `error` (excluded), not as model failures.
