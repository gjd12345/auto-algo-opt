"""Replay the per-round measurement + hypothesis state for finished runs (no API calls).

Usage:
    python measure_rounds.py b4_finding_only a5_finding_only
    python measure_rounds.py b4_finding_only --json
    python measure_rounds.py b4_finding_only --write-state

Reads ``rounds/round_XXXX/evaluation_facts.json`` for each round, re-scores every
candidate on the shared suite at s=1 and s=1e-3, and prints the resulting state
machine. ``--write-state`` stores ``hypotheses_state_recomputed.json`` in the run
directory; nothing else is written.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

import round_activity as ra  # noqa: E402


def replay(run_dir: Path, max_rounds: int | None = None) -> dict:
    discovered = ra.discover_rounds(run_dir)
    state = ra.empty_state()
    rows = []
    prior: set[str] = set()
    complete_ids = discovered["complete_rounds"]
    if max_rounds is not None:
        complete_ids = [rid for rid in complete_ids if rid <= max_rounds]
    for round_id in complete_ids:
        round_dir = run_dir / "rounds" / f"round_{round_id:04d}"
        measure = ra.measure_round(round_dir)
        if measure["baseline_code_sha256"]:
            prior.add(str(measure["baseline_code_sha256"]))
        state = ra.update_state(state, measure, prior_shas=set(prior))
        for cand in measure["candidates"]:
            if cand.get("included") and "generated" in (cand.get("origins") or []):
                prior.add(cand["sha"])
        rendered = ra.render_activity(state, measure, round_id=round_id + 1)
        best = measure["best"] or {}
        row_state = state["rounds"][-1]
        rows.append(
            {
                "round": round_id,
                "candidates": measure["candidate_count"],
                "official_valid": measure["official_valid_count"],
                "official_rejected": measure["official_rejected_count"],
                "probe_failed": measure["probe_failed_count"],
                "included": measure["included_count"],
                "best_nominal": None if not best else round(best.get("nominal", 0.0), 4),
                "best_spread_pct": None if not best else round(best.get("spread_pct", 0.0), 3),
                "best_delta_pct": None
                if not best
                else round(best.get("delta_vs_reference_pct", 0.0), 3),
                "progress_status": row_state.get("progress_status"),
                "status": rendered["status_bits"],
                "finding_summary": rendered["activity"]["finding_summary"],
                "decision_summary": rendered["activity"]["decision_summary"],
            }
        )
    return {
        "run": run_dir.name,
        "discovered_rounds": discovered,
        "rows": rows,
        "state": state,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="*", help="run directory names under runs/")
    parser.add_argument("--json", action="store_true", help="emit one JSON document")
    parser.add_argument(
        "--write-state",
        action="store_true",
        help="write hypotheses_state_recomputed.json into each run directory",
    )
    args = parser.parse_args()

    names = args.runs or ["b4_finding_only"]
    results = []
    for name in names:
        run_dir = HERE / name
        if not run_dir.is_dir():
            print(f"skip {name}: missing")
            continue
        result = replay(run_dir)
        results.append(result)
        if args.write_state and result["rows"]:
            out = run_dir / "hypotheses_state_recomputed.json"
            out.write_text(
                json.dumps(result["state"], indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        if not args.json:
            print(f"\n=== {result['run']}")
            for row in result["rows"]:
                print(
                    f"R{row['round']}  n={row['candidates']:>2}  "
                    f"best={row['best_nominal']}  spread={row['best_spread_pct']}%  "
                    f"vsC={row['best_delta_pct']:+.2f}%  status={row['status']}"
                )

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
