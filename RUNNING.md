# Running a real model (full-suite walkthrough)

This guide walks through kicking off a **fresh, full-suite run** against a real
frontier model end to end. The example uses Anthropic's Haiku, but the same steps
work for any `claude-*` or `gpt-*` model.

A "full-suite" run evaluates the model on **all 16 tasks**, and for each task the
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
   - **Tasks** → leave **all 16** checked (this is the "full suite").

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
- Omitting `--tasks` runs **all 16 tasks** (the full suite).
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

## 6. Run the dashboard in Docker

The dashboard core is pure standard library, so the container needs no build
tooling (no Node/Vite). Build once, then serve:

```bash
docker compose up dashboard          # -> http://localhost:8765
# or without compose:
docker build -t agenteval .
docker run --rm -p 8765:8765 agenteval
```

- To evaluate real models from the container, pass your key:
  `docker run --rm -p 8765:8765 --env-file .env agenteval`.
- Results persist to the host via the `./results` volume (see `docker-compose.yml`).
- Inside the container the server binds `0.0.0.0` (via `--host`); locally it still
  defaults to `127.0.0.1`.

---

## 7. UI test automation

Two layers, both runnable locally or in Docker:
- **API smoke tests** (`tests/test_api.py`) — pure stdlib; verify the JSON
  contract and request validation.
- **Playwright E2E** (`tests/test_e2e.py`) — drive real Chromium: page load,
  Advanced toggle, task selection, the task inspector, and a full keyless
  `reference` run that populates the scorecard.
- **Math unit tests** (`tests/test_math.py`) — grader, perturbations, backends.

Locally:

```bash
pip install -r requirements-dev.txt
playwright install chromium          # one-time browser download
python -m pytest tests -v
```

In Docker (uses the official Playwright image; targets the `dashboard` service):

```bash
docker compose --profile test run --rm tests
```

The tests find the dashboard via `AGENTEVAL_DASHBOARD_URL` if set, otherwise they
start a throwaway server on a free port (writing to a temp results dir, so real
`results/` is untouched).

---

## 8. Math word-problem robustness suite

The same methodology applied to math: take a problem with a known answer, apply a
**semantics-preserving** perturbation (the correct number never changes), and see
whether the answer flips. Grading is numeric (final number vs. gold).

```bash
# keyless demo on the bundled sample (validates the plumbing):
python -m agenteval math --model reference --dataset sample
python -m agenteval math --model brittle-a --dataset sample
python -m agenteval math --model brittle-b --dataset sample   # -> results/math_report.md

# real public data ships in-repo (small verbatim slices), so this works offline:
python -m agenteval math --model claude-haiku-4-5-20251001 --dataset gsm8k

# for a full-scale run, fetch the complete datasets (the loader prefers them):
python -m agenteval fetch-math --dataset gsm8k     # 1319-item test split -> data/math/ (gitignored)
python -m agenteval math --model claude-haiku-4-5-20251001 --dataset gsm8k --limit 200
```

- Datasets: `sample` (original, bundled), plus **real public slices** of `gsm8k`
  and `svamp` committed in-repo (first 25 problems each, MIT-licensed; see
  `agenteval/data/SOURCES.md`). `fetch-math` downloads the full sets into
  `data/math/`, which the loader prefers over the bundled slices. `gsm-plus` ships
  pre-made variants — drop its normalized JSONL in `data/math/gsm-plus.jsonl` and
  the suite uses those variants directly instead of synthesizing perturbations.
- Perturbations: `paraphrase` (control), `verbose`, `distractor`, `noop`,
  `name_swap`, `reformat`. Output reuses the same scorecard engine
  (`results/math_report.md`), so clean/robust accuracy, per-perturbation
  attribution, and cross-model transfer all work.
- Runs checkpoint after every problem, so an interrupted run resumes on re-run.

---

## Troubleshooting

- **"No API key found"** in the dashboard → your key isn't in `.env`, or you
  edited a different `.env`. Confirm the file is at the project root next to
  `requirements.txt`.
- **404 / unknown model** → the model id isn't available to your account. List
  what's available, then use the exact id (e.g. `claude-haiku-4-5-20251001`).
- **A run looks stuck** → check the live log; transient API errors are retried
  automatically and reported as `error` (excluded), not as model failures.
