"""
模块：run_tracker —— 旁路 run 留痕，不改变 EoH 原始输出结构
功能：为每次 run 生成一个标准化的元数据目录（run.json / eval_result.json / rag_trace.json），
      用于事后分析、论文表格、结果 replay。
职责：
  - 创建 run 目录并写入 run.json（入口元数据）
  - 落盘 eval_result / rag_trace / 命令行副本
  - finalize 时写 outcome.json（最终状态 + 最佳代码）
不负责：
  - 调度 run（那是 batch_runner 的事）
  - 评估 objective（由 evaluator.evaluate_run 负责）
  - 读取 EoH 输出的 run_summary（由调用方解析后传入）

调用方：tests/test_run_tracker.py 覆盖;作为旁路留痕工具,由需要标准化元数据的调用方按需接入。

接口：
    RunTracker(base_dir)
        .start_run(suite, problem, arm, gen, rep, run_dir) → Path
        .save_summary(run_dir, summary: dict) → None
        .save_eval(run_dir, eval_result: dict) → None
        .save_rag_trace(run_dir, rag_trace: dict) → None
        .save_command(run_dir, cmd: list[str]) → None
        .finalize(run_dir, status: str, best_code: str = "", objective: float | None = None) → None

输入：run 目录路径 + 各种 dict 数据
输出：JSON 文件落盘

示例：
    tracker = RunTracker("eoh_rag_workspace/runs")
    run_dir = tracker.start_run("island_2", "bp_online", "mixed_rag", gen=8, rep=3,
                                run_dir="/path/to/actual/run")
    tracker.save_eval(run_dir, {"decision": "archive", "improvement": 0.83})
    tracker.finalize(run_dir, status="ok", best_code="def heuristic...", objective=0.00674)
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class RunTracker:
    """旁路 run 留痕：为每次 run 创建结构化元数据目录。"""

    def __init__(self, base_dir: str | Path):
        self._base = Path(base_dir)

    def start_run(
        self,
        suite: str,
        problem: str,
        arm: str,
        gen: int,
        rep: int,
        run_dir: str,
    ) -> Path:
        """创建 run 元数据目录并写入 run.json。返回 tracker 目录路径。"""
        run_tag = f"{problem}_{arm}_g{gen}_r{rep}"
        tracker_dir = self._base / suite / run_tag
        tracker_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "suite": suite,
            "problem": problem,
            "arm": arm,
            "gen": gen,
            "rep": rep,
            "run_dir": run_dir,
            "run_tag": run_tag,
            "started_at": time.time(),
            "status": "running",
        }
        self._write_json(tracker_dir / "run.json", meta)
        return tracker_dir

    def save_summary(self, tracker_dir: str | Path, summary: dict) -> None:
        """落盘 EoH 原始 run_summary 副本。"""
        self._write_json(Path(tracker_dir) / "official_eoh_run_summary.json", summary)

    def save_eval(self, tracker_dir: str | Path, eval_result: dict) -> None:
        """落盘 evaluator 输出。"""
        self._write_json(Path(tracker_dir) / "eval_result.json", eval_result)

    def save_rag_trace(self, tracker_dir: str | Path, rag_trace: dict) -> None:
        """落盘 RAG 上下文追踪信息。"""
        self._write_json(Path(tracker_dir) / "rag_trace.json", rag_trace)

    def save_command(self, tracker_dir: str | Path, cmd: list[str]) -> None:
        """落盘执行命令副本。"""
        self._write_json(Path(tracker_dir) / "command.json", {"cmd": cmd})

    def finalize(
        self,
        tracker_dir: str | Path,
        status: str,
        best_code: str = "",
        objective: float | None = None,
    ) -> None:
        """结束 run，写 outcome.json 并更新 run.json status。"""
        td = Path(tracker_dir)
        outcome: dict[str, Any] = {
            "status": status,
            "finalized_at": time.time(),
        }
        if objective is not None:
            outcome["objective"] = objective
        if best_code:
            outcome["best_code"] = best_code
            (td / "best_code.py").write_text(best_code, encoding="utf-8")
        self._write_json(td / "outcome.json", outcome)

        # 更新 run.json 中的 status
        run_json = td / "run.json"
        if run_json.exists():
            meta = json.loads(run_json.read_text(encoding="utf-8"))
            meta["status"] = status
            meta["finalized_at"] = outcome["finalized_at"]
            self._write_json(run_json, meta)

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


__all__ = ["RunTracker"]
