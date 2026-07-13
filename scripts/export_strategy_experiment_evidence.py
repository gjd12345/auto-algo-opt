"""从 ignored 正式运行目录导出可提交、可审计的 Q3 与 Cross 证据包。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# 允许从仓库根直接执行脚本，无需预先把本项目安装到当前 Python 环境。
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from eoh_rag.experiments.reports.export_strategy_evidence import (
    build_environment,
    collect_dataset_hashes,
    load_formal_runs,
    write_adversarial_candidates,
    write_cross_evidence,
    write_q3_evidence,
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _suite_time_bounds(suite_dir: Path) -> tuple[str, str]:
    """以正式摘要文件的首末落盘时间界定实验窗口，避免依赖会被后续任务覆盖的进程文件。"""

    summary_paths = list(suite_dir.rglob("official_eoh_run_summary.json"))
    if not summary_paths:
        raise FileNotFoundError(f"no formal summaries found under {suite_dir}")
    timestamps = sorted(path.stat().st_mtime for path in summary_paths)
    return (
        datetime.fromtimestamp(timestamps[0]).astimezone().isoformat(),
        datetime.fromtimestamp(timestamps[-1]).astimezone().isoformat(),
    )


def _write_index(output_root: Path) -> None:
    content = """# 正式策略实验证据

- [实验协议](../../docs/experiments/gated_strategy_card_experiments.md)
- [Q3 v2 正式报告](q3_v2/q3_report.md)
- [跨问题迁移正式报告](cross_problem_transfer/cross_report.md)
- [对抗候选数据缺口](adversarial_candidates.json)

原始运行目录受 `.gitignore` 保护；本目录仅保存 manifest 锁、环境白名单、紧凑索引、配对结果、判定与通过安全检查的最佳代码。
"""
    (output_root / "README.md").write_text(content, encoding="utf-8", newline="\n")


def export_all(repository_root: Path) -> dict[str, dict]:
    formal_root = repository_root / "eoh_rag_workspace" / "reports" / "formal"
    manifest_root = repository_root / "eoh_rag_workspace" / "experiments" / "manifests"
    output_root = repository_root / "reports" / "strategy_experiments"

    q3_suite = formal_root / "bp_ablation_cards_q3"
    cross_suite = formal_root / "cross_problem_transfer"
    q3_manifest_path = manifest_root / "bp_ablation_cards_q3.json"
    cross_manifest_path = manifest_root / "cross_problem_transfer_v1.json"
    q3_manifest = _read_json(q3_manifest_path)
    cross_manifest = _read_json(cross_manifest_path)

    q3_started, q3_completed = _suite_time_bounds(q3_suite)
    cross_started, cross_completed = _suite_time_bounds(cross_suite)
    q3_environment = build_environment(
        git_commit="95d4518",
        dataset_hashes=collect_dataset_hashes(q3_manifest, repository_root),
        started_at=q3_started,
        completed_at=q3_completed,
    )
    cross_environment = build_environment(
        git_commit={
            "launch": "0e0de3d",
            "final_compatible": "bce7c1c",
            "note": "后续提交仅修复 TSP held-out 隔离超时；BP/CVRP 运行合同未变。",
        },
        dataset_hashes=collect_dataset_hashes(cross_manifest, repository_root),
        started_at=cross_started,
        completed_at=cross_completed,
    )

    q3_result = write_q3_evidence(
        load_formal_runs(q3_suite, expected_count=30),
        q3_manifest_path,
        output_root / "q3_v2",
        q3_environment,
    )
    cross_result = write_cross_evidence(
        load_formal_runs(cross_suite, expected_count=30),
        cross_manifest_path,
        output_root / "cross_problem_transfer",
        cross_environment,
    )
    write_adversarial_candidates(
        repository_root / "evidence" / "final_batch_20260630" / "shared_pool_snapshot",
        output_root / "adversarial_candidates.json",
    )
    _write_index(output_root)
    return {"q3": q3_result["decision"], "cross": cross_result["decision"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = export_all(args.repository_root.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
