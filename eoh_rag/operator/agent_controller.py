"""
Smart EOH Operator — main controller that ties together:
1. self_repair: compile error auto-fix
2. failure_memory: track and avoid known failure patterns
3. directed_mutate: LLM-driven targeted mutations

It wraps the existing EOH evaluation pipeline, adding intelligence
at the mutation and quality-control layers without replacing the core.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .self_repair import repair_compile_errors
from .failure_memory import FailureMemory
from .directed_mutate import DirectedMutator
from .strategy_templates import generate_template_candidates


# ── metrics that every generation reports ──────────────────────────
METRIC_DEFS = {
    "gen": "Generation index",
    "candidates_generated": "Number of candidates the LLM produced",
    "compiled_ok": "Passed go build (including after self-repair)",
    "compiled_fail": "Still failed after max self-repair attempts",
    "evaluated_ok": "Passed evaluation (valid cost, no timeout)",
    "evaluated_fail": "Failed evaluation (timeout, negative cost, no output)",
    "guard_excluded": "Excluded by candidate guard (suspicious low, etc.)",
    "best_fitness": "Best (lowest) valid cost this generation",
    "avg_fitness": "Average of valid costs this generation",
    "best_vs_baseline_pct": "Improvement over SA baseline (negative = better)",
    "fail_rate": "Fraction of candidates that didn't produce a valid result",
    "repair_count": "Total self-repair attempts across all candidates",
    "repair_success": "Self-repairs that resulted in successful compile",
    "active_failure_patterns": "Failure pattern keys currently active in memory",
    "elapsed_s": "Wall-clock time for this generation",
}


SUSPICIOUS_LOW_RATIO = 0.7


class SmartOperator:
    """Orchestrates intelligent EOH generations with self-repair, failure memory,
    and directed mutation."""

    def __init__(
        self,
        project_root: str,
        api_key: str = "",
        api_endpoint: str = "",
        model: str = "",
        pop_size: int = 4,
        generations: int = 5,
        run_timeout_s: int = 60,
        eva_timeout: int = 120,
        objective_res_weight: float = 0.2,
        dataset_density: str = "d25",
        sim_time_interval: int = 1,
        arrival_scale: float = 1.0,
        use_density_source_dirs: bool = False,
        baseline_cost: float | None = None,
        workspace_dir: str | None = None,
        mutation_mode: str = "llm",
    ):
        self.project_root = Path(project_root).resolve()
        self.pop_size = pop_size
        self.generations = generations
        self.run_timeout_s = run_timeout_s
        self.eva_timeout = eva_timeout
        self.objective_res_weight = objective_res_weight
        self.dataset_density = dataset_density
        self.sim_time_interval = sim_time_interval
        self.arrival_scale = arrival_scale
        self.use_density_source_dirs = use_density_source_dirs
        self.baseline_cost = baseline_cost
        if mutation_mode not in {"llm", "templates", "hybrid"}:
            raise ValueError("mutation_mode must be one of: llm, templates, hybrid")
        self.mutation_mode = mutation_mode

        # Workspace
        ws = Path(workspace_dir) if workspace_dir else self.project_root / "eoh_rag_workspace"
        self.workspace = ws
        self.workspace.mkdir(parents=True, exist_ok=True)

        # Sub-modules
        self.memory = FailureMemory(self.workspace / "operator_memory")
        self.mutator = DirectedMutator(
            api_key=api_key,
            api_endpoint=api_endpoint,
            model=model,
        )

        # State
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.api_endpoint = api_endpoint or os.environ.get("DEEPSEEK_API_ENDPOINT", "api.deepseek.com")
        self.model = model or os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")

        self.generation_log: list[dict[str, Any]] = []
        self.best_candidate: dict[str, Any] | None = None
        self.main_go_text: str | None = None

        self._init_workspace()
        self._load_main_go()

    # ── workspace ───────────────────────────────────────────────────

    def _init_workspace(self) -> None:
        plan = self.workspace / "operator_memory" / "PLAN.md"
        mem = self.workspace / "operator_memory" / "MEMORY.md"
        plan.parent.mkdir(parents=True, exist_ok=True)

        if not plan.exists():
            plan.write_text(
                "# PLAN\n\n## Goal\nEvolve InsertShips via Smart EOH Operator.\n\n"
                "## Current Phase\nInitialization.\n",
                encoding="utf-8",
            )
        if not mem.exists():
            mem.write_text(
                "# MEMORY\n\n## Facts\n- Baseline solver: SA (Simulated Annealing).\n"
                f"- Project root: {self.project_root}\n",
                encoding="utf-8",
            )

    def _load_main_go(self) -> None:
        main_path = self.project_root / "main.go"
        if main_path.exists():
            self.main_go_text = main_path.read_text(encoding="utf-8")

    def _extract_seed_code(self) -> str | None:
        """Extract the current InsertShips function from main.go as the seed."""
        if not self.main_go_text:
            return None
        pat = r"func\s+InsertShips\s*\(.*?\)\s*Dispatch\s*\{[\s\S]*?\n\}"
        m = re.search(pat, self.main_go_text)
        return m.group(0).strip() if m else None

    # ── evaluation integration ──────────────────────────────────────

    def _evaluate_candidate(self, code: str) -> dict[str, Any]:
        """
        Evaluate a single candidate: compile → self-repair → run → guard.
        Returns evaluation record.
        """
        start = time.time()

        # 编译（带自修复）
        repair_result = repair_compile_errors(
            code=code,
            project_root=str(self.project_root),
            api_key=self.api_key,
            api_endpoint=self.api_endpoint,
            model=self.model,
            max_attempts=3,
            base_main_go=self.main_go_text,
        )

        record = {
            "code": code,
            "final_code": repair_result["final_code"],
            "compiled": repair_result["compiled"],
            "repair_count": repair_result["repair_count"],
            "repair_log": repair_result.get("repair_log", []),
            "evaluated": False,
            "cost": None,
            "res_time": None,
            "guard_result": None,
            "error": None,
            "elapsed_s": time.time() - start,
        }

        if not repair_result["compiled"]:
            # Classify the compile error
            last_error = ""
            for entry in reversed(repair_result.get("repair_log", [])):
                last_error = entry.get("error", "")
                if last_error:
                    break
            keys = self.memory.classify_error(last_error)
            for k in keys:
                self.memory.record_failure(k, last_error, code[:300])
            record["error"] = f"compile_failed: {last_error[:300]}"
            self.memory.record_attempt(success=False)
            return record

        # 跑评测（Go 二进制）
        eval_result = self._run_go_evaluation(repair_result.get("patched_main_go", ""))
        record["elapsed_s"] = time.time() - start

        if eval_result.get("timeout"):
            record["error"] = "evaluation_timeout"
            self.memory.classify_error("", runtime_seconds=self.eva_timeout + 1)
            self.memory.record_failure("timeout", "", code[:300])
            self.memory.record_attempt(success=False)
            return record

        cost = eval_result.get("cost")
        res_time = eval_result.get("res_time")
        record["cost"] = cost
        record["res_time"] = res_time
        record["evaluated"] = True

        if cost is None:
            record["error"] = "no_valid_cost"
            self.memory.record_attempt(success=False)
            return record

        # 守卫检查
        guard = self._apply_guard(cost, res_time)
        record["guard_result"] = guard

        if guard["excluded"]:
            self.memory.classify_error("", cost=cost, baseline_cost=self.baseline_cost)
            self.memory.record_failure(guard["reason"], str(cost), code[:300])
            self.memory.record_attempt(success=False)
        else:
            self.memory.record_attempt(success=True)

        return record

    def _run_go_evaluation(self, patched_main_go: str) -> dict[str, Any]:
        """Run the Go solver binary on evaluation data. Uses temporary project."""
        import subprocess
        import tempfile
        import shutil

        tmp = tempfile.mkdtemp(prefix="eoh_eval_")
        try:
            # Write patched main.go
            (Path(tmp) / "main.go").write_text(patched_main_go, encoding="utf-8")

            # Copy supporting files
            for fname in ["routing.go", "go.mod", "go.sum"]:
                src = self.project_root / fname
                if src.exists():
                    shutil.copy2(str(src), os.path.join(tmp, fname))

            # Go build
            build = subprocess.run(
                ["go", "build", "-o", "mainbin.exe", "."],
                cwd=tmp, capture_output=True, text=True, timeout=120,
            )
            if build.returncode != 0:
                return {"cost": None, "timeout": False,
                        "error": f"build failed: {build.stderr[:300]}"}

            # Find evaluation data
            density = str(self.dataset_density).lower()
            data_dir = self.project_root / f"solomon_benchmark_{density}"
            if not data_dir.exists():
                data_dir = self.project_root / "solomon_benchmark"
            if not data_dir.exists():
                return {"cost": None, "timeout": False, "error": "no data directory"}

            json_files = sorted(data_dir.glob("*.json"))[:1]  # first instance only
            if not json_files:
                return {"cost": None, "timeout": False, "error": "no data files"}

            # Run solver
            bin_path = os.path.join(tmp, "mainbin.exe")
            data_path = str(json_files[0])

            try:
                proc = subprocess.run(
                    [bin_path, data_path, "10"],
                    cwd=tmp, capture_output=True, text=True,
                    timeout=self.run_timeout_s,
                )
            except subprocess.TimeoutExpired:
                return {"cost": None, "timeout": True, "error": "run timeout"}

            output = (proc.stdout or "") + "\n" + (proc.stderr or "")

            # Parse output (use lower for both detection and split)
            cost = None
            res = None
            for line in output.splitlines():
                lower = line.lower().strip()
                if lower.startswith("final cost"):
                    try:
                        cost = float(lower.split("final cost", 1)[1].strip())
                    except (ValueError, IndexError):
                        pass
                if lower.startswith("res "):
                    try:
                        res = float(lower.split("res", 1)[1].strip())
                    except (ValueError, IndexError):
                        pass

            return {"cost": cost, "res_time": res, "timeout": False,
                    "returncode": proc.returncode, "stdout": output[:2000]}

        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _apply_guard(self, cost: float, res_time: float | None = None) -> dict[str, Any]:
        """Apply candidate guard rules."""
        if cost is None:
            return {"excluded": True, "reason": "no_cost", "tag": "excluded_no_eoh"}

        if cost < 0:
            return {"excluded": True, "reason": "negative_cost", "tag": "excluded_negative_eoh"}

        if self.baseline_cost and cost < SUSPICIOUS_LOW_RATIO * self.baseline_cost:
            return {"excluded": True, "reason": "suspicious_low", "tag": "excluded_suspicious_low"}

        return {"excluded": False, "reason": "valid", "tag": "valid"}

    def _generate_candidates(
        self,
        parent_code: str,
        overall_best_cost: float | None,
        failure_keys: list[str],
        failure_constraints: str,
    ) -> list[str]:
        """Generate candidates from the configured mutation surface."""
        candidates: list[str] = []

        if self.mutation_mode in {"templates", "hybrid"}:
            template_count = self.pop_size
            if self.mutation_mode == "hybrid":
                template_count = max(1, (self.pop_size + 1) // 2)
            observation = {
                "density": self.dataset_density,
                "arrival_scale": self.arrival_scale,
                "active_failure_patterns": failure_keys,
                "best_cost": overall_best_cost,
                "baseline_cost": self.baseline_cost,
            }
            candidates.extend(generate_template_candidates(observation, template_count))

        if self.mutation_mode in {"llm", "hybrid"} and len(candidates) < self.pop_size:
            llm_candidates = self.mutator.mutate_batch(
                parent_code=parent_code,
                batch_size=self.pop_size - len(candidates),
                current_best_score=overall_best_cost,
                target_score=self.baseline_cost,
                failure_constraints=failure_constraints,
            )
            candidates.extend(llm_candidates)

        # Preserve order while deduplicating exact renders.
        deduped: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            deduped.append(candidate)
            seen.add(candidate)
            if len(deduped) >= self.pop_size:
                break
        return deduped

    # ── generation loop ─────────────────────────────────────────────

    def run(self) -> dict[str, Any]:
        """Run the full Smart EOH Operator loop."""
        seed_code = self._extract_seed_code()
        if not seed_code:
            return {"error": "Could not extract InsertShips seed from main.go"}

        parent_code = seed_code
        overall_best_code = seed_code
        overall_best_cost: float | None = None

        print(f"=== Smart EOH Operator ===")
        print(f"Generations: {self.generations}, Pop size: {self.pop_size}")
        print(f"Mutation mode: {self.mutation_mode}")
        print(f"Density: {self.dataset_density}, Arrival scale: {self.arrival_scale}")
        if self.baseline_cost:
            print(f"Baseline (SA): {self.baseline_cost:.2f}")
        print()

        for gen in range(1, self.generations + 1):
            gen_start = time.time()
            print(f"--- Generation {gen}/{self.generations} ---")

            # Get active failure constraints
            failure_constraints = self.memory.get_constraints_text()
            if failure_constraints:
                print(f"  Active failures: {len(self.memory.get_active_warnings())} patterns")

            # Generate candidates via directed mutation
            failure_keys = [w["key"] for w in self.memory.get_active_warnings()]
            print(f"  Mutating parent (best={overall_best_cost})...")
            candidates = self._generate_candidates(
                parent_code=parent_code,
                overall_best_cost=overall_best_cost,
                failure_keys=failure_keys,
                failure_constraints=failure_constraints,
            )

            gen_metrics = {
                "gen": gen,
                "candidates_generated": len(candidates),
                "compiled_ok": 0,
                "compiled_fail": 0,
                "evaluated_ok": 0,
                "evaluated_fail": 0,
                "guard_excluded": 0,
                "best_fitness": None,
                "avg_fitness": None,
                "best_vs_baseline_pct": None,
                "fail_rate": 0.0,
                "repair_count": 0,
                "repair_success": 0,
                "active_failure_patterns": failure_keys,
                "elapsed_s": 0.0,
                "valid_costs": [],
                "best_code": None,
            }

            # Evaluate each candidate
            valid_records: list[dict[str, Any]] = []
            for i, candidate_code in enumerate(candidates):
                print(f"  Candidate {i+1}/{len(candidates)}: ", end="", flush=True)
                record = self._evaluate_candidate(candidate_code)

                gen_metrics["repair_count"] += record.get("repair_count", 0)
                if record["compiled"]:
                    gen_metrics["compiled_ok"] += 1
                    if record.get("repair_count", 0) > 0:
                        gen_metrics["repair_success"] += 1
                else:
                    gen_metrics["compiled_fail"] += 1
                    print(f"COMPILE FAIL")
                    continue

                if record["evaluated"]:
                    guard = record.get("guard_result", {})
                    if guard.get("excluded"):
                        gen_metrics["guard_excluded"] += 1
                        gen_metrics["evaluated_fail"] += 1
                        print(f"GUARD={guard.get('reason')}")
                    else:
                        gen_metrics["evaluated_ok"] += 1
                        cost = record["cost"]
                        gen_metrics["valid_costs"].append(cost)
                        valid_records.append(record)
                        print(f"cost={cost:.2f}")
                else:
                    gen_metrics["evaluated_fail"] += 1
                    print(f"EVAL FAIL: {record.get('error', 'unknown')[:60]}")

            # Compute generation metrics
            if gen_metrics["valid_costs"]:
                gen_metrics["best_fitness"] = min(gen_metrics["valid_costs"])
                gen_metrics["avg_fitness"] = sum(gen_metrics["valid_costs"]) / len(gen_metrics["valid_costs"])
                if self.baseline_cost:
                    gen_metrics["best_vs_baseline_pct"] = (
                        (gen_metrics["best_fitness"] - self.baseline_cost) / self.baseline_cost * 100
                    )

                # Update overall best
                best_record = min(valid_records, key=lambda r: r.get("cost", float("inf")))
                if overall_best_cost is None or best_record["cost"] < overall_best_cost:
                    overall_best_cost = best_record["cost"]
                    overall_best_code = best_record["final_code"]
                    gen_metrics["best_code"] = best_record["final_code"]

                # Best candidate becomes parent for next generation
                parent_code = best_record["final_code"]
            else:
                gen_metrics["best_fitness"] = None
                gen_metrics["avg_fitness"] = None

            total = gen_metrics["candidates_generated"]
            gen_metrics["fail_rate"] = (total - gen_metrics["evaluated_ok"]) / max(total, 1)
            gen_metrics["elapsed_s"] = round(time.time() - gen_start, 1)

            # Record generation for mutator context
            self.mutator.record_generation({
                "gen": gen,
                "best_fitness": gen_metrics["best_fitness"],
                "avg_fitness": gen_metrics["avg_fitness"],
                "none_rate": gen_metrics["fail_rate"],
                "best_algorithm": "directed_mutation",
                "surviving_strategies": failure_keys,
            })

            self.generation_log.append(gen_metrics)
            self._print_gen_summary(gen_metrics)
            self._save_gen_report(gen, gen_metrics)

        # Final report
        final = self._build_final_report()
        self._save_final_report(final)
        return final

    # ── reporting ───────────────────────────────────────────────────

    def _print_gen_summary(self, m: dict[str, Any]) -> None:
        print(f"  ── Gen {m['gen']} summary ──")
        print(f"  generated={m['candidates_generated']} "
              f"compiled={m['compiled_ok']}/{m['compiled_fail']}fail "
              f"eval_ok={m['evaluated_ok']} guard_excluded={m['guard_excluded']} "
              f"repairs={m['repair_count']}")
        if m["best_fitness"] is not None:
            delta = ""
            if m["best_vs_baseline_pct"] is not None:
                direction = "better" if m["best_vs_baseline_pct"] < 0 else "worse"
                delta = f" (vs baseline: {m['best_vs_baseline_pct']:+.1f}%, {direction})"
            print(f"  best={m['best_fitness']:.2f} avg={m['avg_fitness']:.2f}"
                  f" fail_rate={m['fail_rate']:.0%}{delta}")
        else:
            print(f"  *** ALL CANDIDATES FAILED ***")
        print(f"  elapsed={m['elapsed_s']}s")
        print()

    def _build_final_report(self) -> dict[str, Any]:
        memory_stats = self.memory.get_stats()
        best_cost = None
        best_gen = None
        for g in self.generation_log:
            if g.get("best_fitness") is not None:
                if best_cost is None or g["best_fitness"] < best_cost:
                    best_cost = g["best_fitness"]
                    best_gen = g["gen"]

        return {
            "operator": "SmartEOHOperator",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "config": {
                "generations": self.generations,
                "pop_size": self.pop_size,
                "dataset_density": self.dataset_density,
                "arrival_scale": self.arrival_scale,
                "baseline_cost": self.baseline_cost,
                "mutation_mode": self.mutation_mode,
            },
            "best_cost": best_cost,
            "best_generation": best_gen,
            "baseline_cost": self.baseline_cost,
            "improvement_pct": (
                ((best_cost - self.baseline_cost) / self.baseline_cost * 100)
                if best_cost and self.baseline_cost else None
            ),
            "generation_log": self.generation_log,
            "failure_memory": memory_stats,
            "total_elapsed_s": sum(g.get("elapsed_s", 0) for g in self.generation_log),
        }

    def _save_gen_report(self, gen: int, metrics: dict[str, Any]) -> None:
        report_dir = self.workspace / "operator_memory" / "gen_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / f"gen_{gen:03d}.json"
        path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_final_report(self, final: dict[str, Any]) -> None:
        report_dir = self.workspace / "operator_memory"
        path = report_dir / f"final_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")

        # Also write human-readable summary
        summary_path = report_dir / "latest_summary.md"
        lines = [
            "# Smart EOH Operator — Final Report",
            "",
            f"**Time**: {final['timestamp']}",
            f"**Generations**: {final['config']['generations']}",
            f"**Population size**: {final['config']['pop_size']}",
            f"**Density**: {final['config']['dataset_density']}",
            f"**Arrival scale**: {final['config']['arrival_scale']}",
            "",
            "## Results",
            f"- Best cost: {final['best_cost']}",
            f"- Baseline (SA): {final['baseline_cost']}",
        ]
        if final["improvement_pct"] is not None:
            direction = "improvement" if final["improvement_pct"] < 0 else "degradation"
            lines.append(f"- vs Baseline: {final['improvement_pct']:+.2f}% ({direction})")
        lines.extend([
            "",
            "## Generation History",
            "",
            "| Gen | Best | Avg | Compiled | Eval OK | Guard Excl | Fail Rate | Repairs |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for g in final["generation_log"]:
            lines.append(
                f"| {g['gen']} | {g['best_fitness']} | {g['avg_fitness']} | "
                f"{g['compiled_ok']} | {g['evaluated_ok']} | {g['guard_excluded']} | "
                f"{g['fail_rate']:.0%} | {g['repair_count']} |"
            )
        lines.extend([
            "",
            "## Failure Memory",
            f"- Total attempts: {final['failure_memory']['total_attempts']}",
            f"- Total failures: {final['failure_memory']['total_failures']}",
            f"- Fail rate: {final['failure_memory']['fail_rate']:.1%}",
            "",
            "### Top Failure Patterns",
        ])
        for f in final["failure_memory"].get("top_failures", []):
            lines.append(f"- {f['key']}: {f['count']}×")

        summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Final report: {summary_path}")


# ── CLI entry point ─────────────────────────────────────────────────

def run_operator(
    project_root: str,
    generations: int = 5,
    pop_size: int = 4,
    dataset_density: str = "d25",
    arrival_scale: float = 1.0,
    baseline_cost: float | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Convenience function to run the Smart Operator from CLI or scripts."""
    op = SmartOperator(
        project_root=project_root,
        pop_size=pop_size,
        generations=generations,
        dataset_density=dataset_density,
        arrival_scale=arrival_scale,
        baseline_cost=baseline_cost,
        **kwargs,
    )
    return op.run()
