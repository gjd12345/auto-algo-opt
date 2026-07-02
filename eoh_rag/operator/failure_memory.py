"""
Failure pattern memory: record why candidates fail and inject known
failure patterns into mutation prompts to avoid repeating mistakes.

Tracks categories:
- compile_error: go build failed (undefined type, syntax error, etc.)
- runtime_timeout: solver took too long
- negative_cost: produced negative cost values
- suspicious_low: cost < 0.7 * baseline (likely skipped orders or broken scoring)
- no_feasible: all instances returned invalid cost
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


SUSPICIOUS_LOW_RATIO = 0.7


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
    """Persistent memory of failure patterns across EOH runs."""

    def __init__(self, memory_dir: str | Path):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.memory_dir / "failure_memory.json"
        self._load()

    def _load(self) -> None:
        if self.db_path.exists():
            try:
                data = json.loads(self.db_path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        else:
            data = {}

        self.failures: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "examples": [], "last_seen": None}
        )
        for key, val in data.get("failures", {}).items():
            self.failures[key] = val
        self.stats = data.get("stats", {"total_attempts": 0, "total_failures": 0})

    def _save(self) -> None:
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
        """Classify an error into failure pattern categories. Returns list of keys."""
        matched: list[str] = []

        # Check compile/runtime errors against patterns
        for key, info in FAILURE_PATTERNS.items():
            if info["pattern"] and info["pattern"].lower() in error_text.lower():
                matched.append(key)

        # Check cost-based patterns
        if cost is not None:
            if cost < 0:
                matched.append("negative_cost")
                # Also check for the common cause
                if "RenewnTotalCost" not in error_text:
                    matched.append("missing_renew_total_cost")
            elif baseline_cost is not None and cost < SUSPICIOUS_LOW_RATIO * baseline_cost:
                matched.append("suspicious_low_cost")

        # Check timeout
        if runtime_seconds is not None and runtime_seconds > timeout_threshold:
            matched.append("timeout")

        return list(set(matched))  # deduplicate

    def record_failure(self, key: str, error_snippet: str = "",
                       code_snippet: str = "") -> None:
        """Record a failure occurrence."""
        self.stats["total_failures"] += 1
        entry = self.failures[key]
        entry["count"] += 1
        entry["last_seen"] = datetime.now().isoformat(timespec="seconds")
        if error_snippet and len(entry["examples"]) < 10:
            entry["examples"].append({
                "error": error_snippet[:200],
                "code": code_snippet[:300] if code_snippet else "",
            })

    def record_attempt(self, success: bool) -> None:
        """Record a compile/evaluation attempt."""
        self.stats["total_attempts"] += 1
        if not success:
            self.stats["total_failures"] += 1
        self._save()

    def get_active_warnings(self) -> list[dict[str, str]]:
        """Get currently active failure warnings to inject into prompts."""
        warnings: list[dict[str, str]] = []
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
        """Generate a constraints section for mutation prompts."""
        warnings = self.get_active_warnings()
        if not warnings:
            return ""

        lines = ["\n## Known failure patterns to AVOID\n"]
        lines.append("The following patterns have caused failures in previous runs. DO NOT repeat them:\n")

        for w in warnings[:max_warnings]:
            lines.append(f"- **{w['key']}** ({w['tag']}, seen {w['count']}×): {w['advice']}")

        return "\n".join(lines)

    def get_stats(self) -> dict[str, Any]:
        """Get summary statistics."""
        return {
            "total_attempts": self.stats["total_attempts"],
            "total_failures": self.stats["total_failures"],
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
