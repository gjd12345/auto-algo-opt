"""TOCC V3 — bounded auto-loop pilot.

max_iterations=2, gen≤1, runs≤4. Proposer cannot modify budget.
Defaults to dry-run. Requires --confirm-paid for real API execution.

Flow:
  trace_0 → V2 agent propose → gatekeeper → manifest → (real-run) → trace_1
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from eoh_rag.tocc.contracts import TOCC_CANDIDATE_POOL_STRATEGY

MAX_ITERATIONS = 2


def run_v3_loop(
    start_trace_path: str,
    *,
    problem: str,
    available_cards: list[str],
    output_dir: str,
    max_iterations: int = MAX_ITERATIONS,
    real_run: bool = False,
) -> list[dict[str, Any]]:
    if max_iterations > MAX_ITERATIONS:
        raise ValueError(f"max_iterations ({max_iterations}) exceeds V3 limit ({MAX_ITERATIONS})")

    history: list[dict[str, Any]] = []
    current_trace = start_trace_path
    prev_run_dir = ""

    for iteration in range(1, max_iterations + 1):
        print(f"\n=== V3 iteration {iteration}/{max_iterations} ===")

        # Propose phase: agent reads the trace and proposes an arm
        if not real_run:
            # Dry-run: use V1 rule controller (fast, no API)
            cmd = [
                sys.executable, "-m", "eoh_rag.tocc.controller",
                "--trace", current_trace,
            ]
        else:
            # Real-run: use V2 LLM agent
            cmd = [
                sys.executable, "-m", "eoh_rag.tocc.pipeline",
                "--trace", current_trace,
                "--problem", problem,
                "--available-cards", ",".join(available_cards),
            ]
        print(f"[PROPOSE] reading trace...")
        result = subprocess.run(cmd, text=True, capture_output=True, timeout=120)
        if result.returncode != 0:
            history.append({"iteration": iteration, "error": "proposer failed", "stderr": result.stderr[-500:]})
            break

        proposal_raw = json.loads(result.stdout)

        if not real_run:
            # V1 output: {diagnosis, recommended_cards, recommended_query, ...}
            diagnosis = proposal_raw.get("diagnosis", "unknown")
            cards = proposal_raw.get("recommended_cards", [])
            query = proposal_raw.get("recommended_query", "")
            accepted = bool(cards)
            print(f"[V1] diagnosis={diagnosis}, cards={cards}")
            if not accepted:
                history.append({"iteration": iteration, "diagnosis": diagnosis, "cards": cards, "status": "no_cards_recommended"})
                print(f"[NO CARDS] V1 found no action needed")
                continue
            safe_arm = {
                "name": f"v1_{diagnosis}",
                "runner_arm": "literature_rag",
                "context_strategy": TOCC_CANDIDATE_POOL_STRATEGY,
                "rag_query": query,
                "candidate_card_ids": cards,
            }
            gatekeeper = {}
        else:
            # V2 output: {accepted, safe_arm, gatekeeper, proposal}
            accepted = proposal_raw.get("accepted", False)
            safe_arm = proposal_raw.get("safe_arm")
            gatekeeper = proposal_raw.get("gatekeeper", {})
            cards = (safe_arm.get("candidate_card_ids") or safe_arm.get("selected_card_ids") or []) if safe_arm else []
            query = safe_arm["rag_query"] if safe_arm else ""
            diagnosis = proposal_raw.get("proposal", {}).get("diagnosis", "")
            print(f"[V2] accepted={accepted}, cards={cards}")

        history.append({
            "iteration": iteration,
            "phase": "proposed",
            "diagnosis": diagnosis,
            "cards": cards,
            "accepted": accepted,
        })

        if not accepted or not safe_arm:
            print(f"[REJECTED] violations={gatekeeper.get('violations', [])}")
            break

        cards = safe_arm.get("candidate_card_ids") or safe_arm.get("selected_card_ids") or []
        query = safe_arm["rag_query"]
        print(f"[ACCEPTED] cards={cards}")

        # Write the mini-manifest for this iteration
        suite = f"v3_pilot_iter{iteration}"
        manifest_path = Path(output_dir) / f"{suite}.json"
        manifest = {
            "suite": suite, "model": "JoyAI-LLM-Pro",
            "problems": [problem],
            "arms": [safe_arm],
            "generations": [0], "pop_size": 4, "repeats": 1,
            "max_runs": 1, "max_llm_calls_estimate": 8,
            "require_confirm_for_real_run": True,
            "operators": "i1", "run_timeout_s": 1800,
            "rag": {"top_k": 2, "max_chars": 2500, "prev_run_dir": prev_run_dir},
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        print(f"[MANIFEST] {manifest_path}")

        # Dry-run preview or real execution
        if not real_run:
            print(f"[DRY] cards={cards}, query={query[:80]}...")
            dm_cmd = [
                sys.executable, "-m", "eoh_rag.experiments.batch_runner",
                "--manifest", str(manifest_path),
                "--output-dir", output_dir,
                "--dry-run",
            ]
            subprocess.run(dm_cmd, text=True, timeout=30)
            history[-1]["run_result"] = "dry_run_only"
            current_trace = "(would be new trace)"
            continue

        # Real run
        print(f"[RUN] cards={cards}")
        run_cmd = [
            sys.executable, "-m", "eoh_rag.experiments.batch_runner",
            "--manifest", str(manifest_path),
            "--output-dir", output_dir,
            "--force",
        ]
        proc = subprocess.run(run_cmd, text=True, capture_output=True, timeout=2100)
        history[-1]["run_status"] = "ok" if proc.returncode == 0 else f"exit_{proc.returncode}"
        if proc.returncode != 0:
            history[-1]["run_stderr"] = proc.stderr[-500:]
            print(f"[FAILED] exit={proc.returncode}")
            break

        # Observe the new trace produced by the run
        suite_dir = Path(output_dir) / suite
        index_path = suite_dir / "run_index.json"
        if index_path.exists():
            idx = json.loads(index_path.read_text())
            if idx:
                new_summary = Path(idx[0]["output_dir"]) / "official_eoh_run_summary.json"
                if new_summary.exists():
                    current_trace = str(new_summary)
                    history[-1]["new_trace"] = str(new_summary)
                    history[-1]["best_objective"] = idx[0].get("best_objective")
                    prev_run_dir = idx[0]["output_dir"]
                    print(f"[OBSERVE] best={idx[0].get('best_objective')}")
                else:
                    history[-1]["error"] = "summary not found"; break
            else:
                history[-1]["error"] = "run_index empty"; break
        else:
            history[-1]["error"] = "run_index not found"; break

        time.sleep(1)

    return history


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="TOCC V3 bounded auto-loop pilot")
    parser.add_argument("--trace", required=True)
    parser.add_argument("--problem", required=True)
    parser.add_argument("--cards", required=True)
    parser.add_argument("--output-dir", default="eoh_rag_workspace/reports/auto_experiment_reports/v3_pilot")
    parser.add_argument("--max-iterations", type=int, default=MAX_ITERATIONS)
    parser.add_argument("--confirm-paid", action="store_true",
                        help="Confirm paid API execution (required for real-run)")
    args = parser.parse_args()

    available = [c.strip() for c in args.cards.split(",")]
    output_dir = Path.cwd() / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Safety: require --confirm-paid for real execution
    if args.confirm_paid:
        print("⚠️  CONFIRMED: paid API execution with JoyAI-LLM-Pro")
    else:
        print("DRY-RUN mode (use --confirm-paid for real execution)")

    history = run_v3_loop(
        args.trace, problem=args.problem, available_cards=available,
        output_dir=str(output_dir), max_iterations=args.max_iterations,
        real_run=args.confirm_paid,
    )

    out = output_dir / "v3_loop_history.json"
    out.write_text(json.dumps(history, ensure_ascii=False, indent=2))
    print(f"\nLoop history: {out}")


if __name__ == "__main__":
    main()
