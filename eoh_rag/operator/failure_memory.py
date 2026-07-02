"""
模块：failure_memory（失败模式记忆）
功能：记录 LLM 生成的启发式代码为什么会失败，并把已知的失败模式注入到
      变异（mutation）提示词中，避免后续演化重复犯同样的错误。
职责：
  - 把一次失败归类到若干“失败模式”（编译错误 / 超时 / 负成本 / 成本异常偏低等）；
  - 把失败次数、示例和最近出现时间持久化到 JSON 文件，跨多次演化运行累积；
  - 根据累积的失败统计，生成可直接拼进提示词的“需要避免的问题”约束文本。
接口：
  - 类 FailureMemory(memory_dir)：失败记忆的主入口，负责加载/保存与增删查。
    · classify_error(error_text, cost, baseline_cost, runtime_seconds, timeout_threshold) -> list[str]
    · record_failure(key, error_snippet, code_snippet) -> None
    · record_attempt(success) -> None
    · get_active_warnings() -> list[dict]
    · get_constraints_text(max_warnings) -> str
    · get_stats() -> dict
输入：memory_dir（存放记忆文件的目录）；目录内的 failure_memory.json（如已存在则读取）。
输出：目录下的 failure_memory.json（失败明细 + 统计），以及供提示词使用的约束文本。

失败模式分类说明：
  - compile_error：Go 代码编译失败（未定义类型、语法错误等）
  - runtime_timeout：求解器运行时间过长
  - negative_cost：产生了负的成本值
  - suspicious_low：成本 < 0.7 × 基线（可能漏排订单或评分逻辑被破坏）
  - no_feasible：所有算例都返回了无效成本
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


# 成本“异常偏低”的判定比例：当候选成本低于基线成本的该比例时视为可疑。
SUSPICIOUS_LOW_RATIO = 0.7


# 失败模式表：每个键对应一种失败模式的元数据。
#   tag     —— 归入的失败大类（用于统计与提示展示）
#   pattern —— 在错误文本中用于匹配该模式的子串；为 None 表示该模式不靠文本匹配，
#              而是由评测/守卫逻辑（如成本为负、超时）另行判定
#   advice  —— 给下一轮生成的改进建议，会被拼进提示词以规避此类失败
FAILURE_PATTERNS = {
    "undefined_type": {
        "tag": "compile_error",
        "pattern": "undefined:",
        "advice": "Use only types defined in the codebase: Dispatch, Assign, Station, Ship, RoutingTask, RoutingResult, RoutingStackState. Do NOT invent types like Route, Vehicle, Solution.",
    },
    "sort_manager_missing": {
        "tag": "compile_error",
        "pattern": "SortManager",
        "advice": "If using sort.Sort with SortManager, define the SortManager struct and its Len/Swap/Less methods BEFORE InsertShips.",
    },
    "unused_import": {
        "tag": "compile_error",
        "pattern": "imported and not used",
        "advice": "Remove unused imports. Only import packages actually referenced in code.",
    },
    "undefined_variable": {
        "tag": "compile_error",
        "pattern": "undefined:",
        "advice": "All variables must be declared with var or := before use. Check for typos in variable names.",
    },
    "type_mismatch": {
        "tag": "compile_error",
        "pattern": "cannot use",
        "advice": "Check type compatibility. Station and *Station are different types. Use cal_dis(st1, st2 Station) for distance.",
    },
    "syntax_error": {
        "tag": "compile_error",
        "pattern": "syntax error",
        "advice": "Check for missing braces, parentheses, or semicolons. Ensure func body has matching {}.",
    },
    "negative_cost": {
        "tag": "negative_cost",
        "pattern": None,  # detected by evaluation
        "advice": "Cost must never be negative. Check RemoveShip/AddShip logic. Ensure GenRoute() is called after modifications.",
    },
    "suspicious_low_cost": {
        "tag": "suspicious_low",
        "pattern": None,  # detected by guard
        "advice": "Cost too low (<70% of baseline). Likely the algorithm is skipping ships or exploiting the served-order-only objective. Verify all ships are inserted.",
    },
    "timeout": {
        "tag": "runtime_timeout",
        "pattern": None,  # detected by evaluation
        "advice": "Algorithm took too long. Check for infinite loops. Ensure for loops have bounded iterations. Use MAXASSIGNS or dispatch.AssignsLen as bounds.",
    },
    "missing_renew_total_cost": {
        "tag": "negative_cost",
        "pattern": None,  # detected by cost being 0 or negative
        "advice": "Must call dispatch.RenewnTotalCost() at the end of InsertShips to update TotalCost after modifications.",
    },
}


class FailureMemory:
    """跨演化运行持久化保存的失败模式记忆。

    把每次编译/评测失败按 FAILURE_PATTERNS 归类，累计出现次数并保存到
    memory_dir/failure_memory.json；再据此生成注入变异提示词的“需避免”约束，
    引导后续生成不再重复已知错误。

    参数：
      memory_dir —— 记忆文件所在目录，不存在时自动创建。
    """

    def __init__(self, memory_dir: str | Path):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.memory_dir / "failure_memory.json"
        self._load()

    def _load(self) -> None:
        # 尝试读取已有的记忆文件；文件缺失或解析失败时都退回为空字典，保证可用。
        if self.db_path.exists():
            try:
                data = json.loads(self.db_path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        else:
            data = {}

        # failures 用 defaultdict，任何新出现的失败键都会自动带上初始计数结构。
        self.failures: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "examples": [], "last_seen": None}
        )
        for key, val in data.get("failures", {}).items():
            self.failures[key] = val
        self.stats = data.get("stats", {"total_attempts": 0, "total_failures": 0})

    def _save(self) -> None:
        # 把失败明细与统计整体写回 JSON；ensure_ascii=False 以保留可读的非 ASCII 字符。
        self.db_path.write_text(
            json.dumps(
                {"failures": dict(self.failures), "stats": self.stats},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def classify_error(self, error_text: str, cost: float | None = None,
                       baseline_cost: float | None = None,
                       runtime_seconds: float | None = None,
                       timeout_threshold: float = 120.0) -> list[str]:
        """把一次失败归类到若干失败模式，返回命中的模式键列表。

        参数：
          error_text        —— 编译/运行输出的错误文本，用于按 pattern 子串匹配。
          cost              —— 本次候选的成本；用于识别负成本 / 异常偏低。
          baseline_cost     —— 基线成本；与 cost 比较判断是否“可疑偏低”。
          runtime_seconds   —— 本次运行耗时；超过阈值则判为超时。
          timeout_threshold —— 超时判定阈值（秒）。
        返回：去重后的失败模式键列表（可能为空）。
        """
        matched: list[str] = []

        # 依据文本子串匹配编译/运行类错误（pattern 为 None 的模式在此跳过）。
        for key, info in FAILURE_PATTERNS.items():
            if info["pattern"] and info["pattern"].lower() in error_text.lower():
                matched.append(key)

        # 基于成本的判定：负成本，或相对基线明显偏低。
        if cost is not None:
            if cost < 0:
                matched.append("negative_cost")
                # 负成本的常见根因：漏调用 RenewnTotalCost；错误文本未提及时补记该模式。
                if "RenewnTotalCost" not in error_text:
                    matched.append("missing_renew_total_cost")
            elif baseline_cost is not None and cost < SUSPICIOUS_LOW_RATIO * baseline_cost:
                matched.append("suspicious_low_cost")

        # 基于耗时的超时判定。
        if runtime_seconds is not None and runtime_seconds > timeout_threshold:
            matched.append("timeout")

        return list(set(matched))  # 去重

    def record_failure(self, key: str, error_snippet: str = "",
                       code_snippet: str = "") -> None:
        """记录一次失败：累加次数、刷新最近时间，并保留少量错误/代码片段作为示例。

        每个失败键最多保留 10 条示例；错误片段截断到 200 字符，代码片段截断到 300 字符。
        """
        self.stats["total_failures"] += 1
        entry = self.failures[key]
        entry["count"] += 1
        entry["last_seen"] = datetime.now().isoformat(timespec="seconds")
        # 仅在有错误片段且示例未满 10 条时追加，避免记忆文件无限膨胀。
        if error_snippet and len(entry["examples"]) < 10:
            entry["examples"].append({
                "error": error_snippet[:200],
                "code": code_snippet[:300] if code_snippet else "",
            })

    def record_attempt(self, success: bool) -> None:
        """记录一次编译/评测尝试；失败时同时累加失败计数，并落盘保存。"""
        self.stats["total_attempts"] += 1
        if not success:
            self.stats["total_failures"] += 1
        self._save()

    def get_active_warnings(self) -> list[dict[str, str]]:
        """返回当前生效的失败告警（按出现次数从多到少排序），用于注入提示词。

        仅包含 count 大于 0 的失败模式；每条含 key、tag、count 与改进建议 advice。
        """
        warnings: list[dict[str, str]] = []
        # 按出现次数降序遍历：越常见的失败排在越前面，优先提醒。
        for key, entry in sorted(self.failures.items(),
                                  key=lambda x: x[1].get("count", 0),
                                  reverse=True):
            if entry.get("count", 0) == 0:
                continue
            pattern = FAILURE_PATTERNS.get(key, {})
            warnings.append({
                "key": key,
                "tag": pattern.get("tag", "unknown"),
                "count": entry["count"],
                "advice": pattern.get("advice", ""),
            })
        return warnings

    def get_constraints_text(self, max_warnings: int = 5) -> str:
        """生成可拼进变异提示词的“需避免的失败模式”约束文本段。

        参数 max_warnings 限制最多展示多少条告警；无任何告警时返回空字符串。
        """
        warnings = self.get_active_warnings()
        if not warnings:
            return ""

        lines = ["\n## Known failure patterns to AVOID\n"]
        lines.append("The following patterns have caused failures in previous runs. DO NOT repeat them:\n")

        # 取出现最多的前 max_warnings 条，逐条格式化为一行提示。
        for w in warnings[:max_warnings]:
            lines.append(f"- **{w['key']}** ({w['tag']}, seen {w['count']}×): {w['advice']}")

        return "\n".join(lines)

    def get_stats(self) -> dict[str, Any]:
        """汇总统计：总尝试数、总失败数、失败率，以及出现最多的前 5 种失败。"""
        return {
            "total_attempts": self.stats["total_attempts"],
            "total_failures": self.stats["total_failures"],
            # 失败率；分母用 max(..., 1) 防止尝试数为 0 时除零。
            "fail_rate": (
                self.stats["total_failures"] / max(self.stats["total_attempts"], 1)
            ),
            "top_failures": [
                {"key": k, "count": v.get("count", 0)}
                for k, v in sorted(
                    self.failures.items(),
                    key=lambda x: x[1].get("count", 0),
                    reverse=True,
                )[:5]
                if v.get("count", 0) > 0
            ],
        }
