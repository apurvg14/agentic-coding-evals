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
import json
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
    r.add_argument("--no-report", action="store_true")

    rp = sub.add_parser("report", help="render the scorecard from results.json")
    rp.add_argument("--results", type=Path, default=DEFAULT_OUT / "results.json")
    rp.add_argument("--out", type=Path, default=DEFAULT_OUT / "report.md")

    dh = sub.add_parser("dashboard",
                        help="launch the local web dashboard (no coding required)")
    dh.add_argument("--port", type=int, default=8765)
    dh.add_argument("--no-open", action="store_true", help="don't auto-open the browser")

    args = ap.parse_args()

    if args.cmd == "run":
        only = [t.strip() for t in args.tasks.split(",")] if args.tasks else None
        args.out.mkdir(parents=True, exist_ok=True)
        print(f"Running suite '{args.suite.name}' | model '{args.model}' | "
              f"search={args.search} budget={args.budget} max_size={args.max_size} "
              f"grader={args.grader}")
        results = runner.run_suite(args.suite, args.model, args.out, only=only,
                                   max_steps=args.max_steps, search=args.search,
                                   budget=args.budget, max_size=args.max_size,
                                   grader=args.grader)

        results_path = args.out / "results.json"
        existing = []
        if results_path.exists():
            existing = [r for r in json.loads(results_path.read_text(encoding="utf-8"))
                        if not (r["model"] == args.model
                                and (not only or r["task"] in only))]
        all_results = existing + results
        results_path.write_text(json.dumps(all_results, indent=2), encoding="utf-8")

        if not args.no_report:
            report.render(results_path, args.out / "report.md")
            print(f"\nScorecard -> {args.out / 'report.md'}")
        print(f"Results   -> {results_path}")

    elif args.cmd == "report":
        report.render(args.results, args.out)
        print(f"Scorecard -> {args.out}")

    elif args.cmd == "dashboard":
        from . import dashboard
        dashboard.serve(port=args.port, open_browser=not args.no_open)


if __name__ == "__main__":
    main()
