"""Experiment Manifest Runner.

Reads a JSON manifest, validates it, expands the experiment matrix,
and executes runs via the EOH single-run CLI (eoh_single_runner).

Supports: --dry-run, --no-run, --resume, --force.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Shared Pool 便捷函数
# ---------------------------------------------------------------------------
# 所有跨进程共享池的读写统一由 PoolAPI 承担。
# 下面 4 个 shared_pool_* 函数是围绕 PoolAPI 的轻量便捷封装，各自转发一行调用。
# 内部代码可直接 import PoolAPI。
# ---------------------------------------------------------------------------

from eoh_rag.experiments.pool_api import PoolAPI


def shared_pool_register(pool_dir: Path, problem: str, run_dir: str, objective: float) -> None:
    """便捷封装：转发到 PoolAPI(pool_dir).register_run(...)。"""
    PoolAPI(pool_dir).register_run(problem, run_dir, objective)


def shared_pool_best(pool_dir: Path, problem: str) -> str:
    """便捷封装：转发到 PoolAPI(pool_dir).best_run(problem)。"""
    return PoolAPI(pool_dir).best_run(problem)


def shared_pool_register_code(pool_dir: Path, problem: str, code: str, objective: float) -> None:
    """便捷封装：转发到 PoolAPI(pool_dir).register_code(...)。"""
    PoolAPI(pool_dir).register_code(problem, code, objective)


def shared_pool_best_codes(pool_dir: Path, problem: str, top_k: int = 3) -> list[dict]:
    """便捷封装：转发到 PoolAPI(pool_dir).best_codes(problem, top_k)。"""
    return PoolAPI(pool_dir).best_codes(problem, top_k=top_k)


# ---------------------------------------------------------------------------
# Online Outcome: append outcome records after each successful run
# ---------------------------------------------------------------------------

# Problem baselines for card synthesis threshold —— 统一走 baselines.py
from eoh_rag.experiments.baselines import PROBLEM_BASELINES as _PROBLEM_BASELINES


def _maybe_synthesize_card(pool_dir: str, problem: str, code: str, objective: float) -> None:
    """Auto-synthesize a new card if objective beats baseline by >5%."""
    baseline = _PROBLEM_BASELINES.get(problem)
    if baseline is None:
        return
    improvement = (baseline - objective) / abs(baseline)
    if improvement < 0.05:
        return
    try:
        from eoh_rag.rag.card_synthesis import synthesize_card
        from eoh_rag.rag.schemas import load_corpus, save_corpus
        corpus_path = Path("eoh_rag_workspace/rag/corpus/algorithm_cards.jsonl")
        card = synthesize_card(problem, code, run_info={"objective": objective})
        existing = load_corpus(corpus_path)
        if any(c.id == card.id for c in existing):
            return
        existing.append(card)
        with open(corpus_path, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(card.__dict__, ensure_ascii=False) + "\n")
            fcntl.flock(f, fcntl.LOCK_UN)
    except Exception as e:
        print(f"[WARN] card_synthesis failed: {e}")


def _append_online_outcome(summary_path: Path, problem: str, outcome_file: str) -> None:
    """Extract outcome records from a run summary and append to outcome file."""
    from eoh_rag.rag.card_outcomes import build_outcome_records, save_outcomes
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        rag_trace = data.get("rag_trace") or {}
        run_summary = data.get("run_summary") or {}
        injected = rag_trace.get("rag_injected_items", [])
        if not injected:
            return
        injection_audit = {
            "rag_injected_items": injected,
            "rag_omitted_items": rag_trace.get("rag_omitted_items", []),
        }
        gen_result = {
            "population_size": run_summary.get("population_size", 4),
            "valid_candidates": run_summary.get("valid_candidates", 0),
            "best_objective": run_summary.get("best_objective"),
            "pure_baseline": None,
        }
        records = build_outcome_records(
            run_id=summary_path.parent.name,
            problem=problem,
            generation=run_summary.get("latest_generation", 4),
            injection_audit=injection_audit,
            generation_result=gen_result,
        )
        if records and outcome_file:
            save_outcomes(records, Path(outcome_file), append=True)
    except Exception as e:
        print(f"[WARN] online_outcome_update failed: {e}")

# Reuse existing EOH runner CLI directly
RUNNER_MODULE = "eoh_rag.experiments.eoh_single_runner"

_DEFAULT_PYTHON = os.environ.get("EOH_OFFICIAL_PYTHON", "")
_DEFAULT_ROOT = os.environ.get("EOH_OFFICIAL_ROOT", "")
VALID_ARMS = {"pure_eoh", "api_only", "literature_rag", "history_rag", "mixed_rag", "context_file"}


def _arm_card_ids(arm: dict[str, Any]) -> tuple[list[str], str]:
    if arm.get("candidate_card_ids"):
        return list(arm.get("candidate_card_ids", [])), "candidate_card_ids"
    if arm.get("selected_card_ids"):
        return list(arm.get("selected_card_ids", [])), "selected_card_ids"
    if arm.get("cards"):
        return list(arm.get("cards", [])), "cards"
    return [], "none"


def _validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = ["suite", "problems", "arms"]
    for key in required:
        if key not in manifest:
            errors.append(f"missing required key: {key}")

    arms = manifest.get("arms", [])
    if not isinstance(arms, list) or len(arms) == 0:
        errors.append("arms must be a non-empty list")
    for i, arm in enumerate(arms):
        runner = arm.get("runner_arm", "")
        if runner not in VALID_ARMS:
            errors.append(f"arm[{i}] invalid runner_arm: {runner!r}, must be one of {sorted(VALID_ARMS)}")
        strategy = arm.get("context_strategy", "")
        card_ids, _ = _arm_card_ids(arm)
        if strategy.startswith("tocc_") and not card_ids:
            errors.append(
                f"arm[{i}] tocc_* strategy requires candidate_card_ids, selected_card_ids, or cards"
            )

    problems = manifest.get("problems", [])
    for p in problems:
        if p not in ("bp_online", "tsp_construct", "cvrp_construct"):
            errors.append(f"unknown problem: {p!r}")

    gens = manifest.get("generations", [])
    if isinstance(gens, list) and any(not isinstance(g, int) or g < 0 for g in gens):
        errors.append("generations must be a list of non-negative ints")

    return errors


def _matrix_count(manifest: dict[str, Any]) -> int:
    return (
        len(manifest.get("problems", []))
        * len(manifest.get("arms", []))
        * len(manifest.get("generations", [1]))
        * manifest.get("repeats", 1)
    )


def _build_cmd(
    manifest: dict[str, Any],
    problem: str,
    arm: dict[str, Any],
    generation: int,
    repeat: int,
    output_dir: str,
    prev_run_dir: str = "",
    seed_codes_path: str = "",
) -> list[str]:
    cmd = [
        manifest.get("python_exe") or _DEFAULT_PYTHON or sys.executable,
        "-m",
        RUNNER_MODULE,
        "--problem", problem,
        "--arm", arm["runner_arm"],
        "--pop-size", str(manifest.get("pop_size", 4)),
        "--generations", str(generation),
        "--operators", manifest.get("operators", "i1"),
        "--n-processes", "1",
        "--eval-timeout-s", "40",
        "--llm-timeout-s", "180",
        "--run-timeout-s", str(manifest.get("run_timeout_s", 1800)),
        "--output-dir", output_dir,
        "--official-root", manifest.get("official_root") or _DEFAULT_ROOT,
        "--python", manifest.get("python_exe") or _DEFAULT_PYTHON or sys.executable,
    ]
    rag = {**manifest.get("rag", {}), **arm.get("rag", {})}
    if arm["runner_arm"] in ("literature_rag", "history_rag", "mixed_rag"):
        cmd.extend(["--rag-top-k", str(rag.get("top_k", 2))])
        cmd.extend(["--rag-max-chars", str(rag.get("max_chars", 2500))])
        if arm.get("rag_query"):
            cmd.extend(["--rag-query", arm["rag_query"]])
        card_ids, card_source = _arm_card_ids(arm)
        if card_ids:
            cmd.extend(["--selected-card-ids", ",".join(card_ids)])
            cmd.extend(["--candidate-card-source", card_source])
        if rag.get("use_prev_run_dir_chain"):
            effective_prev = prev_run_dir or rag.get("prev_run_dir", "")
        else:
            effective_prev = rag.get("prev_run_dir", "")
        if effective_prev:
            cmd.extend(["--prev-run-dir", effective_prev])
        if rag.get("outcome_file"):
            cmd.extend(["--outcome-file", str(rag["outcome_file"])])
        if rag.get("rerank_mode"):
            cmd.extend(["--rag-rerank", rag["rerank_mode"]])
        if rag.get("rerank_temperature"):
            cmd.extend(["--rag-rerank-temperature", str(rag["rerank_temperature"])])
        if rag.get("top_fraction") and rag["top_fraction"] != 1.0:
            cmd.extend(["--rag-top-fraction", str(rag["top_fraction"])])
    if seed_codes_path:
        cmd.extend(["--seed-codes", seed_codes_path])
    return cmd


def main() -> None:
    parser = argparse.ArgumentParser(description="Run experiments from a manifest JSON")
    parser.add_argument("--manifest", required=True, help="Path to manifest JSON")
    parser.add_argument("--output-dir", default="eoh_rag_workspace/reports/auto_experiment_reports")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    parser.add_argument("--no-run", action="store_true", help="Validate manifest only")
    parser.add_argument("--resume", action="store_true", help="Skip runs with existing summary")
    parser.add_argument("--force", action="store_true", help="Skip run-count safety check")
    parser.add_argument("--shared-pool-dir", default="", help="Cross-process shared pool for island model population sharing")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.exists():
        sys.exit(f"Manifest not found: {args.manifest}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    errors = _validate_manifest(manifest)
    if errors:
        print("Manifest validation FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    total_runs = _matrix_count(manifest)
    max_runs = manifest.get("max_runs", 2)
    suite = manifest["suite"]
    output_root = Path(args.output_dir).resolve() / suite
    shared_pool_dir = args.shared_pool_dir or ""

    gens = manifest.get("generations", [1])
    has_deep_gen = any(g > 1 for g in gens)
    require_confirm = manifest.get("require_confirm_for_real_run", True)

    if not args.force and not args.dry_run and not args.no_run:
        if total_runs > max_runs:
            print(f"ERROR: expanded runs ({total_runs}) exceed max_runs ({max_runs}).")
            print(f"Use --dry-run to preview, --force to override, or reduce the manifest matrix.")
            sys.exit(1)
        if has_deep_gen:
            print(f"ERROR: generations contain > 1 ({gens}). Deep runs require explicit confirmation.")
            print(f"Use --force to override, or reduce max generation to 0 or 1.")
            sys.exit(1)
        if require_confirm:
            print(f"ERROR: manifest requires confirmation for real runs (require_confirm_for_real_run=true).")
            print(f"Use --force to acknowledge.")
            sys.exit(1)

    if not args.no_run:
        output_root.mkdir(parents=True, exist_ok=True)

    print(f"Suite: {suite}")
    print(f"Matrix: {len(manifest['problems'])}×{len(manifest['arms'])}×{len(manifest.get('generations',[1]))}×{manifest.get('repeats',1)} = {total_runs} runs")
    print()

    run_index: list[dict[str, Any]] = []
    problems = manifest["problems"]
    arms = manifest["arms"]
    generations = manifest.get("generations", [0])
    repeats = manifest.get("repeats", 1)

    for p_idx, problem in enumerate(problems):
        for a_idx, arm in enumerate(arms):
            arm_problems = arm.get("problems", problems)
            if problem not in arm_problems:
                continue
            rag = {**manifest.get("rag", {}), **arm.get("rag", {})}
            for gen in generations:
                prev_run_dir = ""
                for rep in range(1, repeats + 1):
                    run_tag = f"run_{problem}_{arm['name']}_g{gen}_r{rep}"
                    run_out = str(output_root / run_tag)

                    if args.dry_run:
                        cmd = _build_cmd(manifest, problem, arm, gen, rep, run_out, prev_run_dir=prev_run_dir)
                        print(f"[DRY] {run_tag}")
                        print(f"  {' '.join(cmd)}")
                        print()
                        prev_run_dir = run_out
                        continue

                    if args.no_run:
                        continue

                    summary_path = Path(run_out) / "official_eoh_run_summary.json"
                    if args.resume and summary_path.exists():
                        prev = json.loads(summary_path.read_text(encoding="utf-8"))
                        if not prev.get("failure_reason") and prev.get("run_summary", {}).get("ok"):
                            print(f"[SKIP] {run_tag} (already complete)")
                            prev_run_dir = run_out
                            continue
                        else:
                            print(f"[RETRY] {run_tag} (previous run failed: {prev.get('failure_reason','unknown')})")

                    print(f"[RUN] {run_tag}  start={time.strftime('%H:%M:%S')}")
                    # Island model: 从共享池取更优 seed（PoolAPI 统一入口）
                    effective_prev = prev_run_dir
                    seed_codes_path = ""
                    if shared_pool_dir:
                        pool = PoolAPI(shared_pool_dir)
                        pool_best = pool.best_run(problem)
                        if pool_best and pool_best != prev_run_dir:
                            effective_prev = pool_best
                        best_codes = pool.best_codes(problem, top_k=3)
                        if best_codes:
                            seed_codes_path = str(Path(shared_pool_dir) / f"_seed_{problem}_{os.getpid()}.json")
                            Path(seed_codes_path).write_text(json.dumps(best_codes, ensure_ascii=False))
                    cmd = _build_cmd(manifest, problem, arm, gen, rep, run_out, prev_run_dir=effective_prev, seed_codes_path=seed_codes_path)
                    started = time.time()
                    try:
                        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=manifest.get("run_timeout_s", 1800) + 60)
                        status = "ok" if proc.returncode == 0 else f"exit_{proc.returncode}"
                    except subprocess.TimeoutExpired:
                        status = "timeout"
                    elapsed = round(time.time() - started, 1)

                    run_index.append({
                        "tag": run_tag,
                        "problem": problem,
                        "arm": arm["name"],
                        "generation": gen,
                        "repeat": rep,
                        "status": status,
                        "runtime_s": elapsed,
                        "output_dir": run_out,
                    })

                    if summary_path.exists():
                        summary = json.loads(summary_path.read_text(encoding="utf-8"))
                        run_sum = summary.get("run_summary", {})
                        run_index[-1]["best_objective"] = run_sum.get("best_objective")
                        run_index[-1]["valid_candidates"] = run_sum.get("valid_candidates")
                        fail_reason = summary.get("failure_reason")
                        if fail_reason:
                            run_index[-1]["failure_reason"] = fail_reason
                            if status == "ok":
                                run_index[-1]["status"] = "ok_but_summary_failure"

                    print(f"[DONE] {run_tag}  status={status}  elapsed={elapsed}s")
                    if status == "ok" or (summary_path.exists() and json.loads(summary_path.read_text(encoding="utf-8")).get("run_summary", {}).get("ok")):
                        prev_run_dir = run_out
                        # Island model: register successful run in shared pool
                        if shared_pool_dir and summary_path.exists():
                            try:
                                sm = json.loads(summary_path.read_text(encoding="utf-8"))
                                obj = (sm.get("run_summary") or {}).get("best_objective")
                                code = (sm.get("run_summary") or {}).get("best_code", "")
                                if obj is not None:
                                    pool = PoolAPI(shared_pool_dir)
                                    # Adaptive operator: compare BEFORE registering
                                    pool_codes_before = pool.best_codes(problem, top_k=1)
                                    prev_best = pool_codes_before[0]["objective"] if pool_codes_before else None

                                    pool.register_run(problem, run_out, obj)
                                    if code:
                                        pool.register_code(problem, code, obj)
                                        _maybe_synthesize_card(shared_pool_dir, problem, code, obj)

                                    # Register operator result with correct ordering
                                    if prev_best is not None:
                                        improved = obj < prev_best
                                        delta = (prev_best - obj) / abs(prev_best) if prev_best else 0
                                        operators_str = manifest.get("operators", "e1,e2,m1,m2")
                                        pool.register_operator_stat(problem, operators_str, improved, delta)
                            except Exception as e:
                                print(f"[WARN] shared_pool_register failed: {e}")
                        # Online outcome update
                        if summary_path.exists():
                            outcome_file = rag.get("outcome_file", "")
                            if outcome_file:
                                _append_online_outcome(summary_path, problem, outcome_file)
                    else:
                        prev_run_dir = ""
                        # Failure pattern sharing
                        if shared_pool_dir and summary_path.exists():
                            try:
                                sm = json.loads(summary_path.read_text(encoding="utf-8"))
                                rs = sm.get("run_summary") or {}
                                fail_reason = sm.get("failure_reason", "")
                                code = rs.get("best_code", "")
                                if fail_reason and code:
                                    PoolAPI(shared_pool_dir).register_failure(problem, code, fail_reason)
                            except Exception as e:
                                print(f"[WARN] failure_sharing failed: {e}")

    if not args.dry_run and not args.no_run:
        index_path = output_root / "run_index.json"
        index_path.write_text(json.dumps(run_index, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nRun index written to {index_path}")


if __name__ == "__main__":
    main()
