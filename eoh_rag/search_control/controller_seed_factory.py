"""为搜索控制器生成可跨设备重放的多样化初始种群。"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any, Sequence

from eoh_rag.search_control.tsp_controller import (
    ALLOWED_PRIMITIVES,
    MAX_PLAN_STEPS,
    MAX_STEP_BUDGET,
    MAX_TOTAL_BUDGET,
    PRIMITIVE_BUDGET_WEIGHTS,
)


Plan = tuple[tuple[str, int, float], ...]
BASELINE_PLAN: Plan = (
    ("two_opt", 20, 0.0),
    ("relocate", 10, 0.0),
    ("three_opt", 4, 0.0),
)
THRESHOLD_CHOICES = (0.0, 0.0, 0.0, 0.0005, 0.001, 0.002, 0.005)


def generate_random_plan(rng: random.Random) -> Plan:
    """生成合法且接近用满预算的计划，避免初始种群集中在明显欠预算区域。"""

    step_count = rng.randint(2, MAX_PLAN_STEPS)
    primitives = [rng.choice(ALLOWED_PRIMITIVES) for _ in range(step_count)]
    remaining = MAX_TOTAL_BUDGET
    steps: list[tuple[str, int, float]] = []
    for index, primitive in enumerate(primitives):
        weight = PRIMITIVE_BUDGET_WEIGHTS[primitive]
        future_minimum = sum(
            PRIMITIVE_BUDGET_WEIGHTS[item] for item in primitives[index + 1 :]
        )
        maximum = min(MAX_STEP_BUDGET, (remaining - future_minimum) // weight)
        if maximum < 1:
            break
        budget = maximum if index == step_count - 1 else rng.randint(1, maximum)
        steps.append((primitive, budget, rng.choice(THRESHOLD_CHOICES)))
        remaining -= weight * budget
    return tuple(steps)


def _render_plan_code(plan: Plan) -> str:
    """把数据计划渲染成 EOH 种子接口；不引入机器路径或外部教师内容。"""

    return (
        "def build_search_plan(problem_size: int, total_budget: int) -> list:\n"
        "    del problem_size, total_budget\n"
        f"    return {list(plan)!r}\n"
    )


def build_diverse_seed_records(
    base_seed_records: Sequence[dict[str, Any]],
    *,
    total_count: int,
    random_seed: int,
) -> list[dict[str, str]]:
    """保留全部静态种子，再补足确定性随机计划，公平隔离“种群多样性”变量。"""

    if total_count < len(base_seed_records):
        raise ValueError("total_count 不能小于静态种子数量")
    records = [
        {"algorithm": str(item["algorithm"]), "code": str(item["code"])}
        for item in base_seed_records
        if isinstance(item, dict) and item.get("algorithm") and item.get("code")
    ]
    if len(records) != len(base_seed_records):
        raise ValueError("静态种子必须全部包含 algorithm 和 code")

    rng = random.Random(random_seed)
    seen_code = {item["code"].strip() for item in records}
    while len(records) < total_count:
        plan = generate_random_plan(rng)
        code = _render_plan_code(plan)
        if code.strip() in seen_code:
            continue
        index = len(records) - len(base_seed_records) + 1
        records.append(
            {
                "algorithm": (
                    f"Deterministic diverse controller seed {index}; "
                    "generated without held-out feedback."
                ),
                "code": code,
            }
        )
        seen_code.add(code.strip())
    return records


def append_agent_discoveries(
    seed_records: Sequence[dict[str, Any]],
    agent_assets: Sequence[dict[str, Any]],
) -> list[dict[str, str]]:
    """把科研 Agent 已冻结发现追加到种子池，并拒绝 Codex 外部教师混入。"""

    records = [
        {"algorithm": str(item["algorithm"]), "code": str(item["code"])}
        for item in seed_records
    ]
    seen_code = {item["code"].strip() for item in records}
    for asset in agent_assets:
        if asset.get("actor") != "research_agent_eoh":
            raise ValueError(
                f"长期 Agent 种子只接受 research_agent_eoh 资产：{asset.get('asset_id')}"
            )
        code = str(asset.get("code") or "")
        if not code.strip():
            raise ValueError(f"Agent 资产缺少代码：{asset.get('asset_id')}")
        if code.strip() in seen_code:
            continue
        records.append(
            {
                "algorithm": (
                    f"Inherited research-agent discovery {asset.get('asset_id')}: "
                    f"{asset.get('algorithm', '')}"
                ),
                "code": code,
            }
        )
        seen_code.add(code.strip())
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Build deterministic diverse controller seeds")
    parser.add_argument("--base-seed-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--total-count", type=int, default=12)
    parser.add_argument("--random-seed", type=int, default=20260715)
    parser.add_argument("--agent-asset", action="append", default=[])
    args = parser.parse_args()

    base_records = json.loads(Path(args.base_seed_file).read_text(encoding="utf-8"))
    if not isinstance(base_records, list):
        raise ValueError("base-seed-file 必须是 JSON 数组")
    records = build_diverse_seed_records(
        base_records,
        total_count=args.total_count,
        random_seed=args.random_seed,
    )
    agent_assets = [
        json.loads(Path(path).read_text(encoding="utf-8"))
        for path in args.agent_asset
    ]
    records = append_agent_discoveries(records, agent_assets)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output_path.resolve()),
                "base_count": len(base_records),
                "total_count": len(records),
                "random_seed": args.random_seed,
                "agent_asset_count": len(agent_assets),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
