"""Export Phase-0 deduplicated historical run ledger (JSON + CSV) for Milestone 1.5."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "experiments" / "milestone15"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    leg = json.loads((OUT_DIR / "legacy_reproduction_605.json").read_text(encoding="utf-8"))
    scr = json.loads((OUT_DIR / "workbench_screening_605.json").read_text(encoding="utf-8"))

    lineages: list[dict[str, Any]] = [
        {
            "lineage_id": "island605",
            "display_name": "2026-06 三域岛屿并行进化（island605）",
            "date_range": "2026-06-30 ~ 07",
            "raw_dir_count": 732,
            "deduped_status": "core_reproduced_and_abstracted",
            "action": "保留 605 条归档程序；已完成旧协议 604/605 复算（BP #61 差 0.000401）与现行工作台全量初筛；抽象为三域数学家族并精炼入库 12 个代表求解器（CVRP 4 / TSP 4 / OBP 4）",
            "reproducible_in_repo": True,
            "legacy_repro_rate": f"{leg['island605_summary']['total_matched_within_1e4']}/605",
            "notes": "旧协议与现行工作台 OBP 协议存在差异（旧允许主动开新箱，现行仅评已打开箱），双轨分别报告；原始 6 月跑盘日志在 archive，但 605 份程序源码全部完好存于 experiments/island605_archive。",
        },
        {
            "lineage_id": "cvrp_midterm",
            "display_name": "2026-11 主仓 CVRP 闭环实验（experiments/cvrp_midterm）",
            "date_range": "2026-11",
            "raw_dir_count": 148,
            "deduped_status": "core_reproduced_and_provenance_closed",
            "action": "已逐字节核实 R4/R5/R7 在 s2_autonomous_math_r8 原始轮次目录中的真身；24 个仓内非中止会话在 88 题上呈 23 组不同路线（仅 a2_operations_only 与 a3_guided 同指纹），0 个在全部 88 题上等同最近邻（此前 5 个 dev-4 NN 匹配全部位于 _aborted/*）；补录 R4 (s2_r4_cos) 为正式互补候选",
            "reproducible_in_repo": True,
            "legacy_repro_rate": "24/24 in-repo sessions audited; R4/R5/R7 SHA-256 100% matched",
            "notes": "R4 在 select_64 上 22/64 胜 R5，加入 {R5, R7} 使 VBS 降 0.3902%。",
        },
        {
            "lineage_id": "main_outputs_and_evidence",
            "display_name": "2026-11 主仓 outputs/ 与 reports/evidence/",
            "date_range": "2026-11-06 ~ 21",
            "raw_dir_count": 112,
            "deduped_status": "archived_frozen_evidence",
            "action": "reports/evidence（27）为冻结 P0-120/V0/A/B/C 只读证据；outputs/（85）中早期实验与主线重叠，保留历史溯源不重复登记",
            "reproducible_in_repo": True,
            "legacy_repro_rate": "Frozen A/B/C/V0 verified in workbench",
            "notes": "只读红线保护，绝不改动。",
        },
        {
            "lineage_id": "fme_pilot",
            "display_name": "2026-08/09 批量条件扫描（fme_pilot）",
            "date_range": "2026-08-30 ~ 09-06",
            "raw_dir_count": 240,
            "deduped_status": "collapsed_by_condition",
            "action": "非多轮闭环进化，而是 47 种记忆/提示条件在多版本下的重复扫描（1,443 个候选文件）；本仓库不含其原始请求与续跑日志，折叠为条件扫描档案，不把重复候选灌入算法库",
            "reproducible_in_repo": False,
            "legacy_repro_rate": "External worktree only (Refactor0830); archived summary retained",
            "notes": "防止高重复度扫描污染知识库与算法库。",
        },
        {
            "lineage_id": "aao_e2e_and_misc",
            "display_name": "端到端连通冒烟与早期杂项（aao-e2e / agent_ad / optics）",
            "date_range": "2026-07 ~ 11",
            "raw_dir_count": 193,
            "deduped_status": "excluded_non_comparative",
            "action": "属于工程冒烟测试或早期验证，不参与算法方法对比与入库",
            "reproducible_in_repo": False,
            "legacy_repro_rate": "N/A (smoke/harness runs)",
            "notes": "剔除。",
        },
        {
            "lineage_id": "mirrors_and_copies",
            "display_name": "镜像副本与临时批量拷贝（aao-pytemp 238 / Codex 90 / Obsidian 16）",
            "date_range": "2026-09 ~ 11",
            "raw_dir_count": 344,
            "deduped_status": "excluded_duplicate_mirror",
            "action": "纯镜像与 15 份拷贝，彻底去重剔除",
            "reproducible_in_repo": False,
            "legacy_repro_rate": "N/A (duplicate copies)",
            "notes": "占原始扫描真实 run 数的 32%。",
        },
        {
            "lineage_id": "pytest_fixtures",
            "display_name": "自动化单元测试临时夹具（.audit-pytest*）",
            "date_range": "2026-11-21",
            "raw_dir_count": 1071,
            "deduped_status": "excluded_test_fixture",
            "action": "统计前彻底剔除，不计入 1,769 历史 run",
            "reproducible_in_repo": False,
            "legacy_repro_rate": "N/A (pytest temp dirs)",
            "notes": "原始标记扫描 2,108 命中减去 1,071 夹具 = 1,037 常规 run；加上 732 岛屿目录 = 1,769。",
        },
    ]

    payload = {
        "schema_version": "milestone15-run-inventory-deduped/v1",
        "scan_totals": {
            "directories_walked": 49007,
            "marker_hits_raw": 2108,
            "pytest_fixtures_excluded": 1071,
            "marker_real_runs": 1037,
            "island605_supplemental_dirs": 732,
            "total_historical_run_dirs": 1769,
            "mirrors_and_copies_excluded": 344,
            "smoke_and_misc_excluded": 193,
        },
        "errata_resolved": [
            "s2_r5_spiral & s2_r7_iso provenance closed via exact SHA-256 match inside experiments/cvrp_midterm/runs/s2_autonomous_math_r8/rounds/{round_0005,round_0007}.",
            "island605 605 archived programs are directly re-evaluable in-repo (604/605 legacy match; BP #61 differs by 0.000401 due to len(bins) cosine kernel).",
            "Midterm '5 runs degenerated to NN' refined: all 5 dev-4 NN matches are inside _aborted/*; the 24 non-aborted in-repo sessions yield 23 distinct 88-instance route outputs with 0 exact NN across all 88 instances.",
            "HeurAgenix petal_algorithm_b384 confirmed defective on symmetric distance matrices (polar_angle == pi/4 for all customers); replaced by genuine 2D Cartesian Sweep + 2-opt.",
        ],
        "lineages": lineages,
        "midterm_24_sessions": leg["midterm_sessions_audit"]["sessions"],
    }
    (OUT_DIR / "run_inventory_deduped.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    csv_path = OUT_DIR / "run_inventory_deduped.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "lineage_id",
                "display_name",
                "date_range",
                "raw_dir_count",
                "deduped_status",
                "reproducible_in_repo",
                "legacy_repro_rate",
                "action",
                "notes",
            ],
        )
        writer.writeheader()
        for row in lineages:
            writer.writerow(row)
    print(f"Wrote {OUT_DIR / 'run_inventory_deduped.json'} and {csv_path}")


if __name__ == "__main__":
    main()
