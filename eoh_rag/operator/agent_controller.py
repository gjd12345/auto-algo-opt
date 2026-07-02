"""
模块：agent_controller（智能算子主控）
功能：用大模型驱动地演化启发式算法（这里针对 InsertShips 调度函数），在编译、
      评测、变异、质量控制之间串起一整套「生成候选 -> 编译自修复 -> 跑评测 ->
      守卫过滤 -> 记录失败经验 -> 迭代下一代」的进化循环。
职责：
  - 从 main.go 中抽取种子代码（当前的 InsertShips 实现）作为进化起点；
  - 调度三个子模块：self_repair（编译报错自动修复）、failure_memory（记录并规避
    已知失败模式）、directed_mutate（大模型定向变异），另有模板变异作为备选；
  - 在临时工程里编译并运行 Go 求解器，解析出目标成本 cost；
  - 用守卫规则过滤明显异常的候选（负成本、可疑偏低等）；
  - 逐代产出并保存指标报告（JSON + Markdown 汇总）。
接口：
  - SmartOperator(project_root, ...)：核心类，构造后调用 .run() 跑完整进化循环；
  - run_operator(project_root, generations=5, pop_size=4, ...)：便捷入口函数，
    内部创建 SmartOperator 并执行 run()，返回最终报告字典。
输入：
  - project_root 下的 main.go / routing.go / go.mod / go.sum，以及评测数据目录
    solomon_benchmark[_<密度>]/；
  - 大模型访问所需的 api_key / api_endpoint / model（也可由环境变量
    DEEPSEEK_API_KEY / DEEPSEEK_API_ENDPOINT / DEEPSEEK_MODEL 提供）。
输出：
  - 返回最终报告字典（最优成本、各代指标、失败记忆统计等）；
  - 在 workspace/operator_memory/ 下写出逐代 JSON 报告、最终 JSON 报告与
    latest_summary.md 可读汇总。
示例：
  >>> report = run_operator("/path/to/go_project", generations=3, pop_size=4,
  ...                        baseline_cost=1234.5)
  >>> print(report["best_cost"])
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


# ── 每一代都会上报的指标定义（键名 -> 中文/英文含义说明） ──────────────
# 这份字典仅作为指标口径的说明表，供阅读报告时对照，不参与计算逻辑。
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


# 守卫阈值：当候选成本低于「基线成本 × 该比例」时，判定为「可疑偏低」并剔除
# （成本理应越低越好，但过分低往往意味着算法作弊或评测异常，需要过滤）。
SUSPICIOUS_LOW_RATIO = 0.7


class SmartOperator:
    """智能算子主控类：统筹整个启发式进化循环。

    它把「编译自修复、失败记忆、大模型定向变异」三个能力组织起来，逐代生成候选的
    InsertShips 实现、编译并跑评测、用守卫规则过滤异常结果、记录失败经验，最终选出
    成本最低的候选作为下一代父本，并输出各代指标与最终报告。
    """

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
        """初始化主控与各子模块。

        关键参数：
          - project_root：Go 工程根目录（含 main.go 与评测数据目录）。
          - api_key / api_endpoint / model：大模型访问配置，留空则回退到对应环境变量。
          - pop_size：每一代生成的候选数量；generations：进化的总代数。
          - run_timeout_s：单次运行求解器的超时秒数；eva_timeout：评测阶段的超时秒数。
          - dataset_density：评测数据密度（决定优先选用的数据目录）。
          - arrival_scale：到达强度缩放系数（作为观测信息传给变异器）。
          - baseline_cost：SA 基线成本，用于计算改进幅度与守卫阈值。
          - workspace_dir：工作区目录，默认在工程根下的 eoh_rag_workspace。
          - mutation_mode：变异策略，取值 "llm" / "templates" / "hybrid"。
        """
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

        # 工作区：所有中间产物、记忆与报告都写在这里
        ws = Path(workspace_dir) if workspace_dir else self.project_root / "eoh_rag_workspace"
        self.workspace = ws
        self.workspace.mkdir(parents=True, exist_ok=True)

        # 子模块：失败记忆 + 大模型定向变异器
        self.memory = FailureMemory(self.workspace / "operator_memory")
        self.mutator = DirectedMutator(
            api_key=api_key,
            api_endpoint=api_endpoint,
            model=model,
        )

        # 运行时状态：大模型配置留空时回退到环境变量默认值
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.api_endpoint = api_endpoint or os.environ.get("DEEPSEEK_API_ENDPOINT", "api.deepseek.com")
        self.model = model or os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")

        self.generation_log: list[dict[str, Any]] = []  # 逐代指标记录
        self.best_candidate: dict[str, Any] | None = None  # 迄今最优候选
        self.main_go_text: str | None = None  # 缓存的 main.go 全文

        self._init_workspace()
        self._load_main_go()

    # ── workspace ───────────────────────────────────────────────────

    def _init_workspace(self) -> None:
        """初始化工作区里的 PLAN.md 与 MEMORY.md（若不存在则写入初始内容）。"""
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
        """读取并缓存工程根下的 main.go 全文（后续抽取种子、拼接编译都用得到）。"""
        main_path = self.project_root / "main.go"
        if main_path.exists():
            self.main_go_text = main_path.read_text(encoding="utf-8")

    def _extract_seed_code(self) -> str | None:
        """从 main.go 中抽取当前的 InsertShips 函数作为进化种子。

        用正则匹配「func InsertShips(...) Dispatch { ... }」整段函数体；找到返回该
        函数的源码字符串，找不到则返回 None。
        """
        if not self.main_go_text:
            return None
        pat = r"func\s+InsertShips\s*\(.*?\)\s*Dispatch\s*\{[\s\S]*?\n\}"
        m = re.search(pat, self.main_go_text)
        return m.group(0).strip() if m else None

    # ── evaluation integration ──────────────────────────────────────

    def _evaluate_candidate(self, code: str) -> dict[str, Any]:
        """评测单个候选：编译 -> 自修复 -> 运行 -> 守卫，返回一条评测记录字典。

        记录里含最终代码、是否编译成功、修复次数、是否完成评测、成本 cost、
        响应时间 res_time、守卫结果与错误信息等。任何一环失败都会在记录里体现，
        并同步写入失败记忆。
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
            # 编译（含自修复）最终仍失败：归类错误、写入失败记忆后返回
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
            # 评测超时：记为超时类失败
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
            # 跑通了但没解析出有效成本
            record["error"] = "no_valid_cost"
            self.memory.record_attempt(success=False)
            return record

        # 守卫检查：过滤明显异常（如成本可疑偏低）的候选
        guard = self._apply_guard(cost, res_time)
        record["guard_result"] = guard

        if guard["excluded"]:
            # 被守卫剔除：按剔除原因记入失败记忆
            self.memory.classify_error("", cost=cost, baseline_cost=self.baseline_cost)
            self.memory.record_failure(guard["reason"], str(cost), code[:300])
            self.memory.record_attempt(success=False)
        else:
            self.memory.record_attempt(success=True)

        return record

    def _run_go_evaluation(self, patched_main_go: str) -> dict[str, Any]:
        """在临时工程里编译并运行 Go 求解器，解析出成本与响应时间。

        流程：写入打过补丁的 main.go、拷贝依赖文件、go build、挑一个评测数据实例
        运行二进制、从输出里解析 final cost / res。返回含 cost、res_time、timeout、
        error 等键的字典；临时目录在结束时清理。
        """
        import subprocess
        import tempfile
        import shutil

        tmp = tempfile.mkdtemp(prefix="eoh_eval_")
        try:
            # 写入打过补丁的 main.go
            (Path(tmp) / "main.go").write_text(patched_main_go, encoding="utf-8")

            # 拷贝编译所需的其他源文件与依赖清单
            for fname in ["routing.go", "go.mod", "go.sum"]:
                src = self.project_root / fname
                if src.exists():
                    shutil.copy2(str(src), os.path.join(tmp, fname))

            # 编译成可执行文件
            build = subprocess.run(
                ["go", "build", "-o", "mainbin.exe", "."],
                cwd=tmp, capture_output=True, text=True, timeout=120,
            )
            if build.returncode != 0:
                return {"cost": None, "timeout": False,
                        "error": f"build failed: {build.stderr[:300]}"}

            # 定位评测数据目录：优先带密度后缀的目录，回退到通用目录
            density = str(self.dataset_density).lower()
            data_dir = self.project_root / f"solomon_benchmark_{density}"
            if not data_dir.exists():
                data_dir = self.project_root / "solomon_benchmark"
            if not data_dir.exists():
                return {"cost": None, "timeout": False, "error": "no data directory"}

            json_files = sorted(data_dir.glob("*.json"))[:1]  # 只取第一个实例
            if not json_files:
                return {"cost": None, "timeout": False, "error": "no data files"}

            # 运行求解器二进制
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

            # 解析输出（统一转小写，便于识别与切分）
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
        """对候选成本套用守卫规则，判断是否剔除。

        返回含 excluded（是否剔除）、reason（原因）、tag（标签）的字典。剔除条件依次为：
        无成本、负成本、以及成本低于「基线 × SUSPICIOUS_LOW_RATIO」的可疑偏低。
        """
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
        """按配置的变异模式生成本代候选代码列表。

        - templates / hybrid 模式：先用模板生成一批候选（hybrid 只取约一半名额）；
        - llm / hybrid 模式：不足 pop_size 时，再用大模型定向变异补足。
        最后按原顺序去重，并截断到 pop_size 个。
        """
        candidates: list[str] = []

        if self.mutation_mode in {"templates", "hybrid"}:
            template_count = self.pop_size
            if self.mutation_mode == "hybrid":
                template_count = max(1, (self.pop_size + 1) // 2)  # hybrid 下模板占一半名额
            observation = {
                "density": self.dataset_density,
                "arrival_scale": self.arrival_scale,
                "active_failure_patterns": failure_keys,
                "best_cost": overall_best_cost,
                "baseline_cost": self.baseline_cost,
            }
            candidates.extend(generate_template_candidates(observation, template_count))

        if self.mutation_mode in {"llm", "hybrid"} and len(candidates) < self.pop_size:
            # 用大模型补齐剩余名额，并把当前最优、目标与失败约束一并传入
            llm_candidates = self.mutator.mutate_batch(
                parent_code=parent_code,
                batch_size=self.pop_size - len(candidates),
                current_best_score=overall_best_cost,
                target_score=self.baseline_cost,
                failure_constraints=failure_constraints,
            )
            candidates.extend(llm_candidates)

        # 保持原有顺序的同时去除完全重复的候选
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
        """执行完整的进化循环，返回最终报告字典。

        先从 main.go 抽取种子；随后逐代生成候选、评测、更新全局最优、保存各代报告；
        全部完成后汇总并落盘最终报告。若抽不到种子则直接返回错误字典。
        """
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

            # 取出当前生效的失败约束（供变异器规避已知坑）
            failure_constraints = self.memory.get_constraints_text()
            if failure_constraints:
                print(f"  Active failures: {len(self.memory.get_active_warnings())} patterns")

            # 基于父本做定向变异，产出本代候选
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

            # 逐个评测候选，同时累加本代各类计数
            valid_records: list[dict[str, Any]] = []
            for i, candidate_code in enumerate(candidates):
                print(f"  Candidate {i+1}/{len(candidates)}: ", end="", flush=True)
                record = self._evaluate_candidate(candidate_code)

                gen_metrics["repair_count"] += record.get("repair_count", 0)
                if record["compiled"]:
                    gen_metrics["compiled_ok"] += 1
                    if record.get("repair_count", 0) > 0:
                        gen_metrics["repair_success"] += 1  # 靠自修复才编译成功
                else:
                    gen_metrics["compiled_fail"] += 1
                    print(f"COMPILE FAIL")
                    continue

                if record["evaluated"]:
                    guard = record.get("guard_result", {})
                    if guard.get("excluded"):
                        # 评测出结果但被守卫剔除
                        gen_metrics["guard_excluded"] += 1
                        gen_metrics["evaluated_fail"] += 1
                        print(f"GUARD={guard.get('reason')}")
                    else:
                        # 有效候选：记录其成本
                        gen_metrics["evaluated_ok"] += 1
                        cost = record["cost"]
                        gen_metrics["valid_costs"].append(cost)
                        valid_records.append(record)
                        print(f"cost={cost:.2f}")
                else:
                    gen_metrics["evaluated_fail"] += 1
                    print(f"EVAL FAIL: {record.get('error', 'unknown')[:60]}")

            # 汇总本代指标（最优/平均成本、相对基线改进）
            if gen_metrics["valid_costs"]:
                gen_metrics["best_fitness"] = min(gen_metrics["valid_costs"])
                gen_metrics["avg_fitness"] = sum(gen_metrics["valid_costs"]) / len(gen_metrics["valid_costs"])
                if self.baseline_cost:
                    gen_metrics["best_vs_baseline_pct"] = (
                        (gen_metrics["best_fitness"] - self.baseline_cost) / self.baseline_cost * 100
                    )

                # 若本代最优优于全局最优，则更新全局最优
                best_record = min(valid_records, key=lambda r: r.get("cost", float("inf")))
                if overall_best_cost is None or best_record["cost"] < overall_best_cost:
                    overall_best_cost = best_record["cost"]
                    overall_best_code = best_record["final_code"]
                    gen_metrics["best_code"] = best_record["final_code"]

                # 本代最优候选作为下一代的父本
                parent_code = best_record["final_code"]
            else:
                gen_metrics["best_fitness"] = None
                gen_metrics["avg_fitness"] = None

            total = gen_metrics["candidates_generated"]
            gen_metrics["fail_rate"] = (total - gen_metrics["evaluated_ok"]) / max(total, 1)
            gen_metrics["elapsed_s"] = round(time.time() - gen_start, 1)

            # 把本代结果反馈给变异器，供其后续变异时参考
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

        # 全部代数跑完后，汇总并落盘最终报告
        final = self._build_final_report()
        self._save_final_report(final)
        return final

    # ── reporting ───────────────────────────────────────────────────

    def _print_gen_summary(self, m: dict[str, Any]) -> None:
        """在控制台打印某一代的成绩概览（成本、编译/评测计数、耗时等）。"""
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
        """汇总全程结果，构造最终报告字典（含配置、跨代最优成本、失败记忆等）。"""
        memory_stats = self.memory.get_stats()
        best_cost = None
        best_gen = None
        for g in self.generation_log:
            # 跨所有代找出最优（最低）成本及其所在代
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
        """把某一代的指标写成 operator_memory/gen_reports/gen_XXX.json。"""
        report_dir = self.workspace / "operator_memory" / "gen_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / f"gen_{gen:03d}.json"
        path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_final_report(self, final: dict[str, Any]) -> None:
        """落盘最终报告：带时间戳的 JSON，外加一份可读的 latest_summary.md。"""
        report_dir = self.workspace / "operator_memory"
        path = report_dir / f"final_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")

        # 再写一份人类可读的 Markdown 汇总
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
    """便捷入口：从脚本或命令行一步启动整套进化循环。

    关键参数：generations（代数）、pop_size（每代候选数）、dataset_density（数据密度）、
    arrival_scale（到达强度缩放）、baseline_cost（SA 基线成本）；其余大模型/超时等配置
    通过 **kwargs 透传给 SmartOperator。内部构造 SmartOperator 并调用 run()，返回其
    最终报告字典。
    """
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
