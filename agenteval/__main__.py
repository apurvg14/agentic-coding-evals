"""CLI:  python -m agenteval run [options]   |   python -m agenteval report [options]

Examples
  # keyless end-to-end demo (oracle + two brittle agents), then a scorecard:
  python -m agenteval run --model reference
  python -m agenteval run --model brittle-a
  python -m agenteval run --model brittle-b
  python -m agenteval report

  # evaluate a real frontier model (needs ANTHROPIC_API_KEY / OPENAI_API_KEY):
  python -m agenteval run --model claude-3-5-sonnet-latest
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import report, runner

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SUITE = ROOT / "tasks"
DEFAULT_OUT = ROOT / "results"


def main() -> None:
    ap = argparse.ArgumentParser(prog="agenteval")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run the adversarial-robustness eval for a model")
    r.add_argument("--model", default="reference",
                   help="reference | brittle-a | brittle-b | claude-* | gpt-* "
                        "(default: reference, no API key needed)")
    r.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    r.add_argument("--out", type=Path, default=DEFAULT_OUT)
    r.add_argument("--tasks", default=None, help="comma list of task ids to run")
    r.add_argument("--max-steps", type=int, default=14)
    r.add_argument("--search", choices=["greedy", "random", "none"], default="greedy",
                   help="worst-case perturbation search strategy (default: greedy)")
    r.add_argument("--budget", type=int, default=24,
                   help="max perturbation evaluations per task (default: 24)")
    r.add_argument("--max-size", type=int, default=2,
                   help="max perturbations stacked when escalating (default: 2)")
    r.add_argument("--grader", choices=["local", "docker"], default="local",
                   help="grade in a local subprocess or an isolated Docker "
                        "container (SWE-bench style). Default: local")
    r.add_argument("--no-resume", action="store_true",
                   help="ignore saved progress for this model and start fresh "
                        "(default: resume -- reuse completed runs, retry infra errors)")
    r.add_argument("--no-report", action="store_true")

    rp = sub.add_parser("report", help="render the scorecard from results.json")
    rp.add_argument("--results", type=Path, default=DEFAULT_OUT / "results.json")
    rp.add_argument("--out", type=Path, default=DEFAULT_OUT / "report.md")

    mt = sub.add_parser("math",
                        help="run the adversarial-robustness eval on math word problems")
    mt.add_argument("--model", default="reference",
                    help="reference | brittle-a | brittle-b | claude-* | gpt-*")
    mt.add_argument("--dataset", default="sample",
                    help="sample | gsm8k | svamp | gsm-plus | <name> "
                         "(loaded from data/math/<name>.jsonl)")
    mt.add_argument("--data-dir", type=Path, default=None)
    mt.add_argument("--limit", type=int, default=None, help="cap the number of problems")
    mt.add_argument("--out", type=Path, default=DEFAULT_OUT)
    mt.add_argument("--no-resume", action="store_true",
                    help="ignore saved progress for this model and start fresh")
    mt.add_argument("--no-report", action="store_true")

    fm = sub.add_parser("fetch-math",
                        help="download a public math dataset into data/math/")
    fm.add_argument("--dataset", required=True, help="gsm8k | svamp | gsm-plus")
    fm.add_argument("--data-dir", type=Path, default=None)

    dh = sub.add_parser("dashboard",
                        help="launch the local web dashboard (no coding required)")
    dh.add_argument("--port", type=int, default=8765)
    dh.add_argument("--host", default="127.0.0.1",
                    help="interface to bind (default: 127.0.0.1; use 0.0.0.0 in Docker)")
    dh.add_argument("--no-open", action="store_true", help="don't auto-open the browser")

    args = ap.parse_args()

    if args.cmd == "run":
        only = [t.strip() for t in args.tasks.split(",")] if args.tasks else None
        args.out.mkdir(parents=True, exist_ok=True)
        results_path = args.out / "results.json"
        print(f"Running suite '{args.suite.name}' | model '{args.model}' | "
              f"search={args.search} budget={args.budget} max_size={args.max_size} "
              f"grader={args.grader} resume={not args.no_resume}")

        # run_suite checkpoints to results_path after every run (crash-safe), so
        # an interrupted run can be continued by re-running the same command.
        interrupted = False
        try:
            runner.run_suite(args.suite, args.model, args.out, only=only,
                             max_steps=args.max_steps, search=args.search,
                             budget=args.budget, max_size=args.max_size,
                             grader=args.grader, results_path=results_path,
                             resume=not args.no_resume)
        except KeyboardInterrupt:
            interrupted = True
            print("\nInterrupted. Progress saved -- re-run the same command to "
                  "continue from where it stopped.")

        if not args.no_report and results_path.exists():
            report.render(results_path, args.out / "report.md")
            print(f"\nScorecard -> {args.out / 'report.md'}")
        print(f"Results   -> {results_path}")
        if interrupted:
            raise SystemExit(130)

    elif args.cmd == "report":
        report.render(args.results, args.out)
        print(f"Scorecard -> {args.out}")

    elif args.cmd == "math":
        from . import matheval, mathdata
        problems = mathdata.load_dataset(args.dataset, data_dir=args.data_dir,
                                         limit=args.limit)
        args.out.mkdir(parents=True, exist_ok=True)
        results_path = args.out / "math_results.json"
        atoms = matheval.atoms_for(problems)
        print(f"Running math suite | dataset '{args.dataset}' ({len(problems)} problems) "
              f"| model '{args.model}' | resume={not args.no_resume}")

        interrupted = False
        try:
            matheval.run_math_suite(args.model, problems, args.out,
                                    results_path=results_path,
                                    resume=not args.no_resume)
        except KeyboardInterrupt:
            interrupted = True
            print("\nInterrupted. Progress saved -- re-run the same command to continue.")

        math_intro = (
            "Each math word problem is attacked with **semantics-preserving** "
            "perturbations (the correct numeric answer never changes). Grading is "
            "numeric: the final number in the reply is compared to the gold answer. "
            "`robust pass@1` is the **worst-case** -- a problem counts only if it "
            "stayed correct under every perturbation tested. `paraphrase` is a control "
            "that should not break. Infrastructure errors are excluded.")
        if not args.no_report and results_path.exists():
            report.render(results_path, args.out / "math_report.md", atoms=atoms,
                          title="Math Word Problems", intro=math_intro)
            print(f"\nScorecard -> {args.out / 'math_report.md'}")
        print(f"Results   -> {results_path}")
        if interrupted:
            raise SystemExit(130)

    elif args.cmd == "fetch-math":
        from . import mathdata
        out = mathdata.fetch(args.dataset, data_dir=args.data_dir)
        print(f"Fetched '{args.dataset}' -> {out}")

    elif args.cmd == "dashboard":
        from . import dashboard
        dashboard.serve(host=args.host, port=args.port, open_browser=not args.no_open)


if __name__ == "__main__":
    main()
