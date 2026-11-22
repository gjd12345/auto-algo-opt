"""CLI entry point for the Milestone-1 CVRP Workbench backend."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .runner import aggregate_records, run_workbench_evaluation
from .suites import WORKBENCH_BENCHMARKS_DIR, materialize_cvrp_workbench_registry


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m agent_skill_loop.cvrp_workbench",
        description="Build CVRP benchmark suites, run unified multi-paradigm evaluations, and query results.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_suites = sub.add_parser("build-suites", help="Materialize frozen multi-problem suites, published_results, and registry.json")
    p_suites.add_argument("--eohs-root", type=Path, required=True)
    p_suites.add_argument("--cvrplib-root", type=Path, required=True)
    p_suites.add_argument("--eoh-root", type=Path, required=True)
    p_suites.add_argument("--bpplib-extracted-root", type=Path, required=True)
    p_suites.add_argument("--bpplib-solutions-xlsx", type=Path, required=True)
    p_suites.add_argument("--out", type=Path, default=WORKBENCH_BENCHMARKS_DIR)

    p_eval = sub.add_parser("run-eval", help="Run unified 7-algorithm + Direction-2 evaluation and export release bundle")
    p_eval.add_argument("--bundle-dir", type=Path, required=True)
    p_eval.add_argument("--budget-id", default="standard_500ms")
    p_eval.add_argument("--budget-ms", type=float, default=500.0)

    p_summary = sub.add_parser("summary", help="Recompute summary directly from published results/per_instance_records.json")
    p_summary.add_argument("--release", type=Path, required=True)
    p_summary.add_argument("--suite", required=True)
    p_summary.add_argument("--algorithm")
    p_summary.add_argument("--budget-id")

    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    args = _build_parser().parse_args(argv)
    if args.command == "build-suites":
        result = materialize_cvrp_workbench_registry(
            eohs_repo_root=args.eohs_root,
            cvrplib_repo_root=args.cvrplib_root,
            eoh_repo_root=args.eoh_root,
            bpplib_extracted_root=args.bpplib_extracted_root,
            bpplib_solutions_xlsx=args.bpplib_solutions_xlsx,
            output_dir=args.out,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "run-eval":
        result = run_workbench_evaluation(
            args.bundle_dir,
            budget_id=args.budget_id,
            time_budget_ms=args.budget_ms,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "summary":
        rel = args.release
        if rel.name == "current" and rel.is_file() and not rel.is_symlink():
            rel = (rel.parent / rel.read_text(encoding="utf-8").strip()).resolve()
        records_path = rel / "results" / "per_instance_records.json"
        payload = json.loads(records_path.read_text(encoding="utf-8"))
        rows = [
            r for r in payload.get("records", [])
            if r.get("suite_id") == args.suite
            and (not args.algorithm or r.get("algorithm_id") == args.algorithm)
            and (not args.budget_id or r.get("budget_id") == args.budget_id)
        ]
        by_alg: dict[str, list[dict]] = {}
        for r in rows:
            by_alg.setdefault(str(r["algorithm_id"]), []).append(r)
        out = {
            "release": str(rel),
            "suite_id": args.suite,
            "budget_id": args.budget_id or payload.get("budget_id"),
            "algorithms": {alg: aggregate_records(sub) for alg, sub in sorted(by_alg.items())},
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
