"""Assemble heldout results and a comparison report for a controlled pilot.

The pilot itself is already complete when this tool runs.  This tool only
projects persisted Session evidence into three locked selections, evaluates
those selections against the registered heldout suite, rebuilds the reports,
and exports compact evidence bundles.  It never contacts a provider.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Mapping

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_skill_loop import session_runtime as db
from agent_skill_loop.benchmark import (
    ExperimentManifest,
    FrozenSelection,
    PopulationSnapshot,
    build_archive_from_session,
    build_report,
    evaluate_selection,
    freeze_selection,
    load_profile_suite,
)
from agent_skill_loop.skill_store import load_skill
from tools.export_benchmark_evidence import export_bundle
from tools.generation_diagnostics import derive_generation_diagnostics


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def freeze_to_disk(path: Path, selection: FrozenSelection) -> None:
    """Persist selection before any heldout access; never replace a prior lock."""
    with path.open("x", encoding="utf-8") as stream:
        json.dump({**selection.as_dict(), "content_hash": selection.content_hash}, stream,
                  ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def evaluate_locked(path: Path, expected_hash: str, heldout: Mapping[str, Any]) -> tuple:
    selection = FrozenSelection.from_dict(_load(path))
    if selection.content_hash != expected_hash:
        raise ValueError("persisted_selection_changed")
    # A crash after this marker is an unknown evaluation attempt, never an
    # implicit retry. Recovery must record a separate evaluation attempt.
    marker = path.with_suffix(".heldout-started.json")
    with marker.open("x", encoding="utf-8") as stream:
        json.dump({"selection_sha256": selection.content_hash}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    result = evaluate_selection(selection, heldout)
    _save(path.with_suffix(".heldout-result.json"), result)
    return selection, result


def _manifest(session: Path) -> ExperimentManifest:
    config = _load(session / "config_frozen.json")
    raw = config["experiment_manifest"]
    document = raw.get("document", raw.get("manifest", raw))
    return ExperimentManifest(
        **{
            key: value
            for key, value in document.items()
            if key not in {"schema_version", "sha256", "experiment_manifest_sha256"}
        }
    )


def _last_round(session: Path) -> int:
    rounds = [
        int(path.name.split("_")[-1])
        for path in (session / "rounds").glob("round_*")
        if path.is_dir() and path.name.split("_")[-1].isdigit()
    ]
    if not rounds:
        raise ValueError("pilot_rounds_missing")
    return max(rounds)


def _facts(session: Path) -> list[dict[str, Any]]:
    result = []
    for path in sorted((session / "rounds").glob("round_*/evaluation_facts.json")):
        result.append(_load(path))
    if not result:
        raise ValueError("pilot_evaluation_facts_missing")
    return result


def _request_stats(session: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    con = sqlite3.connect(session / "session.sqlite3")
    con.row_factory = sqlite3.Row
    try:
        rows = [dict(row) for row in con.execute(
            "SELECT request_id,sequence,round_id,purpose,state,input_tokens,output_tokens,elapsed_seconds,error_code,finish_reason "
            "FROM requests ORDER BY sequence"
        )]
    finally:
        con.close()
    def token_total(name: str) -> int | None:
        values = [row[name] for row in rows if isinstance(row.get(name), int) and row[name] >= 0]
        return sum(values) if values else None
    by_purpose: dict[str, int] = Counter(str(row["purpose"]) for row in rows)
    completed = sum(row.get("state") == "complete" for row in rows)
    stats = {
        "provider_requests": len(rows),
        "completed_requests": completed,
        "input_tokens": token_total("input_tokens"),
        "output_tokens": token_total("output_tokens"),
        "elapsed_seconds": round(sum(float(row.get("elapsed_seconds") or 0.0) for row in rows), 3),
        "requests_by_purpose": dict(sorted(by_purpose.items())),
    }
    return stats, rows


def _training_stats(facts: list[dict[str, Any]]) -> dict[str, Any]:
    generated: list[Mapping[str, Any]] = []
    valid_generated: list[Mapping[str, Any]] = []
    invalid_errors: Counter[str] = Counter()
    rounds: list[dict[str, Any]] = []
    for fact in facts:
        candidates = fact.get("candidates", [])
        round_generated = [
            row for row in candidates
            if row.get("origin") in {"generated", "generated_repair"}
        ]
        round_valid = [row for row in round_generated if row.get("valid") is True]
        for row in round_generated:
            generated.append(row)
            if row.get("valid") is True:
                valid_generated.append(row)
            else:
                invalid_errors[str(row.get("error_code") or "unknown")] += 1
        generated_hashes = [str(row["code_sha256"]) for row in round_valid if row.get("code_sha256")]
        dual = fact.get("dual_budget") or {}
        rounds.append({
            "round_id": fact.get("round_id"),
            "generated": len(round_generated),
            "valid_generated": len(round_valid),
            "best_generated_fitness": min(
                (float(row["objective"]) for row in round_valid if row.get("objective") is not None),
                default=None,
            ),
            "incumbent_after": fact.get("incumbent_after"),
            "dual_budget": dual,
            "distinct_valid_code_count": len(set(generated_hashes)),
        })
    objectives = [float(row["objective"]) for row in valid_generated if row.get("objective") is not None]
    hashes = [str(row["code_sha256"]) for row in valid_generated if row.get("code_sha256")]
    return {
        "rounds": rounds,
        "generated_candidates": len(generated),
        "valid_generated_candidates": len(valid_generated),
        "invalid_generated_candidates": len(generated) - len(valid_generated),
        "generated_valid_rate": (len(valid_generated) / len(generated)) if generated else None,
        "distinct_valid_generated_code_count": len(set(hashes)),
        "duplicate_valid_generated_code_count": len(hashes) - len(set(hashes)),
        "best_generated_fitness": min(objectives) if objectives else None,
        "invalid_error_counts": dict(sorted(invalid_errors.items())),
    }


def _selection_members(
    kind: str,
    session: Path,
    archive: Mapping[str, Any],
    metric_spec_hash: str,
    last_round: int,
) -> FrozenSelection:
    snapshot_path = session / "rounds" / f"round_{last_round:04d}" / "population_snapshot.json"
    snapshot = PopulationSnapshot.from_dict(_load(snapshot_path))
    if kind == "incumbent_top1":
        facts = _load(session / "rounds" / f"round_{last_round:04d}" / "evaluation_facts.json")
        incumbent = facts.get("incumbent_after") or {}
        ref = incumbent.get("ref")
        if not isinstance(ref, str) or not ref:
            raise ValueError("incumbent_reference_missing")
        skill = load_skill(session / ref)
        return FrozenSelection(
            selection_kind=kind,
            members=(
                {
                    "code": skill.code,
                    "code_sha256": skill.code_sha256,
                    "objective": float(incumbent["objective"]),
                    "origin": skill.origin,
                },
            ),
            training_metric_spec_hash=metric_spec_hash,
            source_ref=ref,
        )
    if kind == "archive_topk":
        return freeze_selection(
            kind,
            archive["entries"],
            metric_spec_hash=metric_spec_hash,
            k=10,
            source_ref="archive.json",
        )
    return freeze_selection(
        "final_population_set",
        archive["entries"],
        metric_spec_hash=metric_spec_hash,
        population_snapshot=snapshot,
        source_ref=str(snapshot_path.relative_to(session)),
    )


def _prepare_group(group_root: Path, evidence_root: Path) -> dict[str, Any]:
    session = group_root / "session"
    manifest = _manifest(session)
    facts = _facts(session)
    last_round = _last_round(session)
    state = db.read_state(run=session)
    archive = build_archive_from_session(session)
    training = _training_stats(facts)
    request_stats, requests = _request_stats(session)
    diagnostics = derive_generation_diagnostics(session, requests)
    config = _load(session / "config_frozen.json")
    benchmark = config["benchmark"]
    report_dir = group_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=False)
    selections: dict[str, Any] = {}
    locked = {}
    for kind in ("incumbent_top1", "archive_topk", "final_population_set"):
        selection = _selection_members(kind, session, archive, manifest.metric_spec_hash, last_round)
        freeze_to_disk(report_dir / f"{kind}.selection.json", selection)
        locked[kind] = selection.content_hash
    # Freeze every training-derived choice before even loading heldout data.
    heldout = load_profile_suite(benchmark["id"], benchmark["profile"], split="heldout")
    for kind, expected_hash in locked.items():
        selection, test = evaluate_locked(report_dir / f"{kind}.selection.json", expected_hash, heldout)
        identity = {
            "experiment_manifest_sha256": manifest.content_hash,
            "selection_sha256": selection.content_hash,
        }
        metrics = {
            **identity,
            "metric_spec_hash": manifest.metric_spec_hash,
            "selection_kind": kind,
            "best_training_fitness": min(float(item["objective"]) for item in selection.members),
            "training": training,
            "heldout_aggregate_fitness": test.get("aggregate_fitness"),
        }
        budget = {**state["result"]["budgets"], **identity}
        inputs = {
            "manifest": manifest.as_dict(),
            "selection": {**selection.as_dict(), "content_hash": selection.content_hash},
            "metrics": metrics,
            "budget": budget,
            "test_result": test,
        }
        _save(report_dir / f"{kind}.inputs.json", inputs)
        persisted = _load(report_dir / f"{kind}.inputs.json")
        persisted["manifest"] = ExperimentManifest(
            **{key: value for key, value in persisted["manifest"].items() if key != "schema_version"}
        )
        persisted["selection"] = FrozenSelection.from_dict(persisted["selection"])
        report = build_report(**persisted)
        _save(report_dir / f"{kind}.report.json", report)
        # Rebuild from the serialized input once more, so the report is a
        # proof over the persisted evidence rather than only in-memory data.
        persisted_again = _load(report_dir / f"{kind}.inputs.json")
        persisted_again["manifest"] = ExperimentManifest(
            **{key: value for key, value in persisted_again["manifest"].items() if key != "schema_version"}
        )
        persisted_again["selection"] = FrozenSelection.from_dict(persisted_again["selection"])
        if build_report(**persisted_again) != report:
            raise ValueError(f"report_reload_mismatch:{kind}")
        selections[kind] = {
            "selection_sha256": selection.content_hash,
            "member_count": len(selection.members),
            "training_best_fitness": metrics["best_training_fitness"],
            "heldout_aggregate_fitness": test.get("aggregate_fitness"),
            "heldout_complete": test.get("complete_instance_coverage"),
            "test_evaluation_attempts": test.get("test_evaluation_attempts"),
        }
    evidence_dir = evidence_root / group_root.name
    export_bundle(session, evidence_dir, report_dir=report_dir)
    result = {
        "group": group_root.name,
        "run_id": state["run_id"],
        "experiment_manifest_sha256": manifest.content_hash,
        "inheritance_mode": manifest.inheritance_mode,
        "agent_guidance": manifest.agent_guidance,
        "run_state": state["run_state"],
        "round_count": last_round,
        "termination_reason": state["task"].get("terminal_reason"),
        "training": training,
        "budget": state["result"]["budgets"],
        "requests": request_stats,
        "generation_diagnostics": diagnostics["generation"],
        "archive_entry_count": archive["entry_count"],
        "selections": selections,
        "report_dir": str(report_dir),
        "evidence_dir": str(evidence_dir),
    }
    _save(group_root / "comparison.json", result)
    return result


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _markdown(results: list[Mapping[str, Any]], root: Path) -> str:
    lines = [
        "# OBP v1.1 A/B/C/D 真实 API Pilot 比较报告",
        "",
        "> 本报告由独立 Session 的持久化证据重建。预算见各组实际记录；heldout 在 selection 持久化并重载后离线执行，未产生模型请求。",
        "",
        "## 运行摘要",
        "",
        "| 组 | 轮数 | 总评测 | 生成候选（有效率） | seed 重评 | Provider 请求 | 最好生成训练 fitness | incumbent 训练 fitness | heldout Top1 | heldout archive Top10 | heldout final population |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in results:
        training = item["training"]
        budget = item["budget"]
        selections = item["selections"]
        rate = training["generated_valid_rate"]
        rate_text = "—" if rate is None else f"{training['valid_generated_candidates']}/{training['generated_candidates']} ({rate:.1%})"
        lines.append(
            "| {group} | {rounds} | {total} | {generated} | {seed} | {requests} | {best} | {inc} | {top1} | {archive} | {population} |".format(
                group=item["group"],
                rounds=item["round_count"],
                total=budget.get("total_evaluation_attempts", "—"),
                generated=rate_text,
                seed=budget.get("seed_reevaluation_attempts", "—"),
                requests=item["requests"].get("provider_requests", "—"),
                best=_fmt(training.get("best_generated_fitness")),
                inc=_fmt(selections["incumbent_top1"]["training_best_fitness"]),
                top1=_fmt(selections["incumbent_top1"]["heldout_aggregate_fitness"]),
                archive=_fmt(selections["archive_topk"]["heldout_aggregate_fitness"]),
                population=_fmt(selections["final_population_set"]["heldout_aggregate_fitness"]),
            )
        )
    lines += [
        "",
        "## 预算与链路核对",
        "",
        "| 组 | novel candidate | seed reevaluation | baseline | repair | archive 条目 | 终止原因 | token（输入/输出） |",
        "|---|---:|---:|---:|---:|---:|---|---:|",
    ]
    for item in results:
        budget = item["budget"]
        requests = item["requests"]
        lines.append(
            "| {group} | {novel} | {seed} | {baseline} | {repair} | {archive} | `{stop}` | {input}/{output} |".format(
                group=item["group"], novel=budget.get("novel_candidate_evaluations", "—"),
                seed=budget.get("seed_reevaluation_attempts", "—"),
                baseline=budget.get("baseline_attempts", "—"),
                repair=budget.get("repair_attempts", "—"),
                archive=item["archive_entry_count"], stop=item["termination_reason"],
                input=requests.get("input_tokens", "—"), output=requests.get("output_tokens", "—"),
            )
        )
    lines += [
        "",
        "## 逐组结果",
        "",
    ]
    for item in results:
        training = item["training"]
        lines += [
            f"### Group {item['group']}",
            "",
            f"- Session `{item['run_id']}`，manifest `{item['experiment_manifest_sha256']}`。继承模式：`{item['inheritance_mode']}`；Agent guidance：`{str(item['agent_guidance']).lower()}`。",
            f"- 训练终止：`{item['termination_reason']}`；实际评测 {item['budget'].get('total_evaluation_attempts')} 次；archive 发现条目 {item['archive_entry_count']} 个。",
            f"- 生成候选：{training['valid_generated_candidates']}/{training['generated_candidates']} 有效；不同有效代码 {training['distinct_valid_generated_code_count']} 个；重复有效代码 {training['duplicate_valid_generated_code_count']} 个。",
            f"- 最好生成训练 fitness：`{_fmt(training['best_generated_fitness'])}`；主要无效原因：`{training['invalid_error_counts'] or 'none'}`。",
            "- Heldout：" + "; ".join(
                f"{kind}={_fmt(data['heldout_aggregate_fitness'])} ({data['test_evaluation_attempts']} evals)"
                for kind, data in item["selections"].items()
            ) + ".",
            f"- 证据包：`{item['evidence_dir']}`。",
            "",
        ]
    lines += [
        "## 解释边界",
        "",
        "1. 历史 D（D0）为固定脚本指导，不是反馈驱动的 Coding Agent 决策；agent_guidance=true 只证明开关启用。D1 必须由 Coding Agent 读取事实并提交 Plan/Evaluate。",
        "2. A/B 是单轮连续与分轮 baseline 的整体比较；历史 C/D0 只比较固定指导 treatment，不能解释为 Agent 自适应能力的增益。",
        "3. 本次每组只有一个真实 run，结果用于验证闭环、继承、预算和证据链，不足以作统计显著性或泛化结论。heldout 分数只对注册的 OBP mini 套件有效。",
        "4. `0.0` 是该 mini 套件上相对 reference 的 mean relative gap；它表示达到该套件 reference，不代表跨数据集或更大实例上的普遍优势。",
        "",
        "## 证据索引",
        "",
        f"- Pilot 根目录：`{root}`",
        "- 每组 `reports/` 下有 `incumbent_top1`、`archive_topk`、`final_population_set` 的 selection、inputs 和 report。",
        "- 每组 `evidence/` 是可校验的 compact bundle，包含训练事实、种群、预算和 heldout report。",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    pilot_root = args.pilot_root.resolve()
    runs_root = pilot_root / "runs"
    evidence_root = pilot_root / "evidence"
    results = [_prepare_group(runs_root / group, evidence_root) for group in ("A", "B", "C", "D")]
    summary = {
        "schema_version": "algorithm-optimization-controlled-pilot-comparison/v1",
        "pilot_root": str(pilot_root),
        "provider_requests_during_reporting": 0,
        "groups": results,
    }
    _save(pilot_root / "comparison_summary.json", summary)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(_markdown(results, pilot_root), encoding="utf-8")
    print(json.dumps({"report": str(args.report.resolve()), "summary": str((pilot_root / 'comparison_summary.json').resolve()), "provider_requests": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
