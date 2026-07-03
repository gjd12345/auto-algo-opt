"""
模块：PoolAPI —— 跨进程共享池的统一读写门面
功能：把 shared_pool_* 系列读写函数收敛到单一 API，向上暴露稳定接口，
      统一维护共享池的读写语义。
职责：
  - 维护 pool_dir 目录下的 5 类 JSONL 文件的 append/read 语义
    * pool_index.jsonl               —— 已完成 run 索引（problem, run_dir, objective）
    * best_codes_<problem>.jsonl     —— 精英代码池（seed_codes 用）
    * operator_stats_<problem>.jsonl —— 算子成功率统计（e1/e2/m1/m2）
    * failures_<problem>.jsonl       —— 失败模式 + 短提示
  - 所有写入使用跨平台 advisory lock 保证多进程安全
  - 读取时按目标值升序聚合（objective 越小越好，minimize 语义）
不负责：
  - 决定谁应该 register（由 batch_runner / hooks 决定）
  - card synthesis / 语料库落盘（由 rag.card_synthesis 处理）
  - 具体 problem 的 baseline 阈值（由 experiments.baselines 提供）
主要调用方：
  - eoh_rag.experiments.batch_runner
  - eoh_rag.experiments.hooks
  - eoh_rag.rag.retriever（读取 best_codes 作为 history_rag 语料）

接口：
    class PoolAPI:
        __init__(pool_dir: str | Path)
        register_run(problem, run_dir, objective, **meta) -> None
        best_run(problem) -> str
        list_runs(problem=None) -> list[dict]
        register_code(problem, code, objective, **meta) -> None
        best_codes(problem, top_k=3) -> list[dict]
        register_operator_stat(problem, operator, improved, delta) -> None
        operator_weights(problem) -> dict[str, float]
        register_failure(problem, code, failure_type, pattern_hint="") -> None
        failure_hints(problem, top_k=5) -> list[str]

输入：pool_dir 目录路径（若不存在会在首次写入时自动 mkdir -p）
输出：JSONL 文件；查询接口返回 dict / list[dict] / str

示例：
    from eoh_rag.experiments.pool_api import PoolAPI
    pool = PoolAPI("eoh_rag_workspace/shared_pool")
    pool.register_run("bp_online", "/path/to/run", 0.0250)
    best = pool.best_run("bp_online")               # 返回 run_dir 字符串
    codes = pool.best_codes("bp_online", top_k=3)   # 返回 [{code, objective, ts}]
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from eoh_rag.utils.file_lock import exclusive_lock


class PoolAPI:
    """Shared-pool 统一门面（见模块头）。线程/进程安全通过跨平台文件锁保证。"""

    def __init__(self, pool_dir: str | Path) -> None:
        self.pool_dir = Path(pool_dir)

    # ------------------------------------------------------------------ #
    # 内部工具                                                            #
    # ------------------------------------------------------------------ #

    def _ensure_dir(self) -> None:
        self.pool_dir.mkdir(parents=True, exist_ok=True)

    def _append_jsonl(self, path: Path, record: dict[str, Any]) -> None:
        """文件锁 append 一条 JSONL；ensure_ascii=False 允许中文。"""
        self._ensure_dir()
        line = json.dumps(record, ensure_ascii=False)
        with open(path, "a", encoding="utf-8") as f:
            with exclusive_lock(f):
                f.write(line + "\n")

    def _read_jsonl(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        entries: list[dict] = []
        with open(path, "r", encoding="utf-8") as f:
            with exclusive_lock(f):
                text = f.read()
        for line in text.strip().split("\n"):
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    # ------------------------------------------------------------------ #
    # 路径                                                                #
    # ------------------------------------------------------------------ #

    def _pool_index_path(self) -> Path:
        return self.pool_dir / "pool_index.jsonl"

    def _best_codes_path(self, problem: str) -> Path:
        return self.pool_dir / f"best_codes_{problem}.jsonl"

    def _operator_stats_path(self, problem: str) -> Path:
        return self.pool_dir / f"operator_stats_{problem}.jsonl"

    def _failures_path(self, problem: str) -> Path:
        return self.pool_dir / f"failures_{problem}.jsonl"

    # ------------------------------------------------------------------ #
    # Run 索引                                                            #
    # ------------------------------------------------------------------ #

    def register_run(
        self,
        problem: str,
        run_dir: str,
        objective: float,
        **meta: Any,
    ) -> None:
        """把一次完成的 run 追加到 pool_index.jsonl。"""
        record: dict[str, Any] = {
            "problem": problem,
            "run_dir": run_dir,
            "objective": objective,
            "ts": time.time(),
        }
        if meta:
            record.update(meta)
        self._append_jsonl(self._pool_index_path(), record)

    def best_run(self, problem: str) -> str:
        """返回该 problem 目前 objective 最小的 run_dir；无则返回 ''。"""
        best_obj = float("inf")
        best_dir = ""
        for entry in self._read_jsonl(self._pool_index_path()):
            if entry.get("problem") != problem:
                continue
            try:
                obj = float(entry.get("objective"))
            except (TypeError, ValueError):
                continue
            if obj < best_obj:
                best_obj = obj
                best_dir = entry.get("run_dir", "")
        return best_dir

    def list_runs(self, problem: str | None = None) -> list[dict]:
        """返回 pool_index.jsonl 中匹配 problem 的所有 entry；problem=None 则全量。"""
        entries = self._read_jsonl(self._pool_index_path())
        if problem is None:
            return entries
        return [e for e in entries if e.get("problem") == problem]

    # ------------------------------------------------------------------ #
    # 精英代码池                                                          #
    # ------------------------------------------------------------------ #

    def register_code(
        self,
        problem: str,
        code: str,
        objective: float,
        **meta: Any,
    ) -> None:
        """把一段高质量代码追加到 best_codes_<problem>.jsonl。"""
        record: dict[str, Any] = {
            "code": code,
            "objective": objective,
            "ts": time.time(),
        }
        if meta:
            record.update(meta)
        self._append_jsonl(self._best_codes_path(problem), record)

    def best_codes(self, problem: str, top_k: int = 3) -> list[dict]:
        """按 objective 升序返回去重 top_k 条精英代码。"""
        entries = self._read_jsonl(self._best_codes_path(problem))
        entries.sort(key=lambda x: x.get("objective", float("inf")))
        seen: set[float] = set()
        unique: list[dict] = []
        for e in entries:
            obj = e.get("objective")
            if obj in seen:
                continue
            seen.add(obj)
            unique.append(e)
            if len(unique) >= top_k:
                break
        return unique

    # ------------------------------------------------------------------ #
    # 算子成功率                                                          #
    # ------------------------------------------------------------------ #

    def register_operator_stat(
        self,
        problem: str,
        operator: str,
        improved: bool,
        delta: float,
    ) -> None:
        """记录一次算子（e1/e2/m1/m2）应用后的改进/退化信号。"""
        self._append_jsonl(
            self._operator_stats_path(problem),
            {
                "operator": operator,
                "improved": bool(improved),
                "delta": float(delta),
                "ts": time.time(),
            },
        )

    def operator_weights(self, problem: str) -> dict[str, float]:
        """返回每个算子的采样权重（[0.5, 1.5]），样本 < 3 时给默认 1.0。

        权重公式与既有算子权重规则保持一致：
            success_rate = success / total
            weight = 0.5 + success_rate       when total >= 3
                   = 1.0                       otherwise
        """
        entries = self._read_jsonl(self._operator_stats_path(problem))
        stats: dict[str, dict[str, int]] = defaultdict(
            lambda: {"success": 0, "total": 0}
        )
        for e in entries:
            op = e.get("operator")
            if not op:
                continue
            stats[op]["total"] += 1
            if e.get("improved"):
                stats[op]["success"] += 1

        weights: dict[str, float] = {}
        for op, s in stats.items():
            if s["total"] >= 3:
                weights[op] = 0.5 + s["success"] / s["total"]
            else:
                weights[op] = 1.0
        return weights

    # ------------------------------------------------------------------ #
    # 失败模式                                                            #
    # ------------------------------------------------------------------ #

    def register_failure(
        self,
        problem: str,
        code: str,
        failure_type: str,
        pattern_hint: str = "",
    ) -> None:
        """记录一次代码失败模式（timeout/invalid_output/runtime_error 等）。"""
        if not pattern_hint:
            pattern_hint = self._extract_pattern(code, failure_type)
        self._append_jsonl(
            self._failures_path(problem),
            {
                "failure_type": failure_type,
                "pattern_hint": pattern_hint,
                "code_hash": hashlib.sha1(code.encode()).hexdigest()[:12],
                "ts": time.time(),
            },
        )

    def failure_hints(self, problem: str, top_k: int = 5) -> list[str]:
        """按出现频次返回 top_k 条失败提示（用于注入 LLM prompt）。"""
        entries = self._read_jsonl(self._failures_path(problem))
        counter: Counter[str] = Counter()
        for e in entries:
            hint = e.get("pattern_hint", "")
            if hint:
                counter[hint] += 1
        return [hint for hint, _ in counter.most_common(top_k)]

    # ------------------------------------------------------------------ #
    # 失败模式提示提取（内部）                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_pattern(code: str, failure_type: str) -> str:
        """从失败代码中提取一句可读的短提示。"""
        if failure_type == "eval_timeout":
            if re.search(r"for .+ in .+:\s*\n\s*for", code):
                return "AVOID nested loops over all nodes (causes timeout)"
            if "while" in code and "break" not in code:
                return "AVOID unbounded while loops without break condition"
            return "AVOID O(n^3) or higher complexity operations"
        if failure_type == "invalid_output":
            if "return None" in code or "return []" in code:
                return "MUST return valid output (not None or empty)"
            return "ENSURE return value matches expected type and range"
        if failure_type == "runtime_error":
            if "/ 0" in code or "divide" in code.lower():
                return "AVOID division by zero — add epsilon to denominators"
            return "CHECK array index bounds and division operations"
        if failure_type == "valid_collapse":
            return "AVOID strategies that produce identical outputs for all inputs"
        return f"AVOID pattern causing {failure_type}"


__all__ = ["PoolAPI"]
