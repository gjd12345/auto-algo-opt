"""冻结抽象策略资产的 schema、去问题化和两臂公平性校验。"""
from __future__ import annotations
import json, re
from pathlib import Path

FORBIDDEN = re.compile(r"\b(?:bp|tsp|cvrp|scorebin|select_next_node)\b|\w+\([^)]*\)", re.I)

def load_and_validate_assets(strategy_path: Path, map_path: Path) -> tuple[dict, dict]:
    strategies=json.loads(strategy_path.read_text(encoding="utf-8")); mapping=json.loads(map_path.read_text(encoding="utf-8"))
    rows=strategies.get("strategies", [])
    if len(rows) != 12: raise ValueError("exactly 12 abstract strategies are required")
    ids={row["abstract_strategy_id"] for row in rows}
    if len(ids) != 12: raise ValueError("abstract strategy ids must be unique")
    for row in rows:
        if row.get("schema_version") != "abstract-strategy/v1" or len(row.get("source_content_sha256", "")) != 64: raise ValueError("invalid abstract strategy schema or hash")
        if FORBIDDEN.search(row.get("abstract_description", "")): raise ValueError(f"strategy not de-problematized: {row['abstract_strategy_id']}")
    for problem, config in mapping.get("problems", {}).items():
        if len(config.get("core_local", [])) != 2 or len(config.get("extra_local", [])) != 2 or len(config.get("external_abstract", [])) != 2: raise ValueError(f"unbalanced card budget: {problem}")
        if not set(config["external_abstract"]).issubset(ids): raise ValueError(f"unknown external strategy: {problem}")
    if mapping.get("max_chars") != 2500: raise ValueError("max_chars must be 2500")
    return strategies, mapping
