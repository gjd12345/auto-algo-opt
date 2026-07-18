"""从现有事实源生成问题集、进化算法与选择器资产清单。

该脚本只聚合已有注册表、manifest、正式资产和合同，不复制算法代码，也不对
候选质量重新排名。这样可以让科研 Agent 使用一个可审计的视图，同时避免手工
Markdown 中的问题数量和算法状态随仓库演进而漂移。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

# 允许从任意当前目录直接执行脚本，同时仍从仓库内导入唯一问题注册表。
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eoh_rag.eoh_runner.registry import PROBLEM_SPECS
from eoh_rag.experiments.problem_registry import PROBLEMS, RUNNABLE_PROBLEMS


DEFAULT_JSON_OUTPUT = "agent_records/inventories/research_assets_v1.json"
DEFAULT_MARKDOWN_OUTPUT = "agent_records/inventories/research_assets_v1.md"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _relative_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _infer_manifest_problems(path: Path, payload: dict[str, Any]) -> tuple[list[str], str]:
    """读取 manifest 声明的问题；旧清单无字段时才按稳定命名规则推断。

    推断来源会写进输出，避免把历史命名约定伪装成显式数据合同。
    """

    if isinstance(payload.get("problems"), list):
        return sorted({str(value) for value in payload["problems"]}), "declared"
    if isinstance(payload.get("problem"), str):
        return [payload["problem"]], "declared"

    haystack = f"{path.stem} {payload.get('suite', '')}".lower()
    if "cvrp_expert_router" in haystack:
        return ["cvrp_expert_router"], "inferred_from_name"
    if "tsp_search_controller" in haystack:
        return ["tsp_search_controller"], "inferred_from_name"
    if (
        haystack.startswith("bp_")
        or "bp_online" in haystack
        or "bin_packing" in haystack
        or haystack.startswith("adaptive_bp")
        or haystack.startswith("warm_")
    ):
        return ["bp_online"], "inferred_from_name"
    if "cvrp" in haystack:
        return ["cvrp_construct"], "inferred_from_name"
    if "tsp" in haystack:
        return ["tsp_construct"], "inferred_from_name"
    return [], "unclassified"


def _manifest_inventory(root: Path) -> dict[str, Any]:
    manifest_root = root / "eoh_rag_workspace" / "experiments" / "manifests"
    records: list[dict[str, Any]] = []
    by_problem: dict[str, list[str]] = defaultdict(list)
    classification_counts: Counter[str] = Counter()

    for path in sorted(manifest_root.glob("*.json")):
        payload = _read_json(path)
        # core benchmark registry 是数据哈希目录，不是实验 manifest。
        if payload.get("schema_version") == "core-benchmarks/v1":
            continue
        problems, classification = _infer_manifest_problems(path, payload)
        relative = _relative_path(path, root)
        records.append(
            {
                "path": relative,
                "suite": payload.get("suite"),
                "problems": problems,
                "problem_classification": classification,
            }
        )
        classification_counts[classification] += 1
        for problem in problems:
            by_problem[problem].append(relative)

    return {
        "manifest_file_count": len(records),
        "classification_counts": dict(sorted(classification_counts.items())),
        "problem_occurrence_counts": {
            problem: len(paths) for problem, paths in sorted(by_problem.items())
        },
        "records": records,
    }


def _current_problem_catalog(root: Path, manifest_inventory: dict[str, Any]) -> list[dict[str, Any]]:
    paths_by_problem: dict[str, list[str]] = defaultdict(list)
    for record in manifest_inventory["records"]:
        for problem in record["problems"]:
            paths_by_problem[problem].append(record["path"])

    catalog = []
    for problem in RUNNABLE_PROBLEMS:
        official_spec = PROBLEMS.get(problem)
        catalog.append(
            {
                "problem_id": problem,
                "execution_tier": "current_formal_runner",
                "registry_source": "eoh_rag.experiments.problem_registry.RUNNABLE_PROBLEMS",
                "objective_direction": (
                    official_spec.objective_direction if official_spec is not None else "minimize"
                ),
                "target_function": (
                    official_spec.target_function
                    if official_spec is not None
                    else {
                        "tsp_search_controller": "build_search_plan",
                        "cvrp_expert_router": "select_expert",
                    }[problem]
                ),
                "manifest_occurrences": len(paths_by_problem.get(problem, [])),
                "manifest_paths": sorted(paths_by_problem.get(problem, [])),
            }
        )
    return catalog


def _legacy_problem_catalog(root: Path) -> list[dict[str, Any]]:
    catalog = []
    for problem_id, spec in sorted(PROBLEM_SPECS.items()):
        source_status = [
            {
                "path": source,
                "exists": (root / source).exists(),
            }
            for source in spec.source_files
        ]
        catalog.append(
            {
                "problem_id": problem_id,
                "execution_tier": "legacy_go_runner",
                "registry_source": "eoh_rag.eoh_runner.registry.PROBLEM_SPECS",
                "language": spec.language,
                "objective_direction": spec.objective_direction,
                "source_files": source_status,
                "benchmark_data": spec.benchmark_data,
                "default_metrics": spec.default_metrics,
                "registered_in_current_formal_runner": problem_id in RUNNABLE_PROBLEMS,
            }
        )
    return catalog


def _core_benchmark_inventory(root: Path) -> dict[str, Any]:
    registry_path = (
        root
        / "eoh_rag_workspace"
        / "experiments"
        / "manifests"
        / "core_benchmark_registry.json"
    )
    payload = _read_json(registry_path)
    counts: Counter[str] = Counter()
    missing_paths: list[str] = []
    hash_mismatches: list[str] = []
    for record in payload["instances"]:
        counts[record["problem"]] += 1
        path = root / record["path"]
        if not path.exists():
            missing_paths.append(record["path"])
        elif _sha256_file(path).lower() != record["sha256"].lower():
            hash_mismatches.append(record["path"])
    return {
        "registry_path": _relative_path(registry_path, root),
        "instance_counts": dict(sorted(counts.items())),
        "instance_count": sum(counts.values()),
        "missing_paths": missing_paths,
        "hash_mismatches": hash_mismatches,
    }


def _problem_from_asset_id(asset_id: str) -> str:
    if asset_id.startswith("bp_online"):
        return "bp_online"
    if asset_id.startswith("tsp_search_controller"):
        return "tsp_search_controller"
    return "unknown"


def _experiment_algorithm_assets(root: Path) -> list[dict[str, Any]]:
    asset_root = root / "eoh_rag_workspace" / "experiments" / "assets"
    records = []
    for path in sorted(asset_root.glob("*.json")):
        payload = _read_json(path)
        asset_id = payload.get("asset_id")
        if not asset_id:
            continue
        code = payload.get("code")
        declared_hash = payload.get("best_code_sha256") or payload.get("code_sha256")
        actual_hash = _sha256_text(code) if isinstance(code, str) else None
        if declared_hash and actual_hash:
            hash_status = (
                "verified" if declared_hash.upper() == actual_hash.upper() else "mismatch"
            )
        elif declared_hash:
            hash_status = "declared_without_inline_code"
        else:
            hash_status = "not_declared"
        selection = payload.get("selection") if isinstance(payload.get("selection"), dict) else {}
        confirmation = (
            payload.get("confirmation") if isinstance(payload.get("confirmation"), dict) else {}
        )
        records.append(
            {
                "asset_id": asset_id,
                "problem_id": _problem_from_asset_id(asset_id),
                "source_path": _relative_path(path, root),
                "actor_raw": payload.get("actor", "Unknown"),
                "origin": payload.get("origin", "Unknown"),
                "declared_roles": [
                    value.strip()
                    for value in str(payload.get("asset_role", "")).split(",")
                    if value.strip()
                ],
                "declared_code_sha256": declared_hash,
                "computed_code_sha256": actual_hash,
                "code_hash_status": hash_status,
                "formal_seed_allowed": selection.get("formal_seed_allowed"),
                "confirmation_gate_passed": confirmation.get("gate_passed"),
                "selector_pool_id": None,
            }
        )
    return records


def _router_expert_assets(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    contract_path = (
        root
        / "official_eoh"
        / "examples"
        / "cvrp_expert_router"
        / "router_contract_v1.json"
    )
    contract = _read_json(contract_path)
    records = []
    for expert in contract["experts"]:
        source_path = root / expert["source_file"]
        candidates = _read_json(source_path)
        candidate = next(
            (item for item in candidates if item.get("candidate_id") == expert["expert_id"]),
            None,
        )
        actual_hash = _sha256_text(candidate["code"]) if candidate else None
        hash_status = (
            "verified"
            if actual_hash and actual_hash.upper() == expert["code_sha256"].upper()
            else "mismatch"
        )
        records.append(
            {
                "asset_id": f"cvrp_expert_router_v1:{expert['expert_id']}",
                "problem_id": "cvrp_construct",
                "source_path": expert["source_file"],
                "actor_raw": expert["actor"],
                "origin": "automatic_evolution",
                "declared_roles": ["selector_expert"],
                "declared_code_sha256": expert["code_sha256"],
                "computed_code_sha256": actual_hash,
                "code_hash_status": hash_status,
                "formal_seed_allowed": True,
                "confirmation_gate_passed": None,
                "selector_pool_id": contract["contract_id"],
                "summary": expert["summary"],
            }
        )
    selector_pool = {
        "contract_id": contract["contract_id"],
        "contract_path": _relative_path(contract_path, root),
        "scientific_actor": contract["scientific_actor"],
        "selector_problem_id": "cvrp_expert_router",
        "target_problem_id": "cvrp_construct",
        "expert_ids": contract["expert_ids"],
        "feature_order": contract["feature_order"],
        "development_split": contract["data_split"]["development"],
        "confirmation_split": contract["data_split"]["confirmation"],
        "confirmation_visible_during_evolution": contract["data_split"][
            "confirmation_visible_during_evolution"
        ],
        "held_out_used": contract["data_split"]["held_out_used"],
    }
    return selector_pool, records


def _cross_problem_best_assets(root: Path) -> list[dict[str, Any]]:
    index_path = (
        root
        / "reports"
        / "strategy_experiments"
        / "cross_problem_transfer"
        / "best_codes"
        / "index.json"
    )
    records = []
    for item in _read_json(index_path):
        code_path = index_path.parent.parent / item["file"]
        records.append(
            {
                "asset_id": f"cross_problem_transfer:{item['problem']}:{item['arm']}",
                "problem_id": item["problem"],
                "source_path": _relative_path(code_path, root),
                "actor_raw": "Unknown",
                "origin": "frozen_cross_problem_transfer_output",
                "declared_roles": ["experiment_best_code"],
                "declared_code_sha256": None,
                "computed_code_sha256": _sha256_file(code_path),
                "code_hash_status": "computed_file_hash_only",
                "formal_seed_allowed": None,
                "confirmation_gate_passed": None,
                "selector_pool_id": None,
                "run_key": item["run_key"],
                "score": item["score"],
            }
        )
    return records


def _knowledge_asset_inventory(root: Path) -> dict[str, Any]:
    cards_path = root / "eoh_rag_workspace" / "rag" / "corpus" / "algorithm_cards.jsonl"
    kind_counts: Counter[str] = Counter()
    valid_records = 0
    for line in cards_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        valid_records += 1
        kind_counts[str(payload.get("kind", "Unknown"))] += 1
    return {
        "algorithm_cards_path": _relative_path(cards_path, root),
        "record_count": valid_records,
        "kind_counts": dict(sorted(kind_counts.items())),
        "evidence_boundary": (
            "RAG cards are retrieval knowledge, not automatically verified excellent algorithms."
        ),
    }


def _deduplicate_algorithms(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_hash: dict[str, list[str]] = defaultdict(list)
    for record in records:
        code_hash = record.get("computed_code_sha256")
        if code_hash:
            by_hash[code_hash.upper()].append(record["asset_id"])
    duplicate_groups = {
        code_hash: sorted(asset_ids)
        for code_hash, asset_ids in sorted(by_hash.items())
        if len(asset_ids) > 1
    }
    return {
        "record_count": len(records),
        "records_with_computed_hash": sum(bool(item.get("computed_code_sha256")) for item in records),
        "unique_computed_code_hashes": len(by_hash),
        "duplicate_hash_groups": duplicate_groups,
    }


def build_inventory(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifests = _manifest_inventory(root)
    selector_pool, router_assets = _router_expert_assets(root)
    algorithm_records = (
        _experiment_algorithm_assets(root)
        + router_assets
        + _cross_problem_best_assets(root)
    )
    algorithm_records.sort(key=lambda item: item["asset_id"])
    return {
        "schema_version": "research_asset_inventory/v1",
        "generated_by": "scripts/research_asset_inventory.py",
        "generation_policy": (
            "Deterministic aggregation only; no scientific ranking and no raw population ingestion."
        ),
        "problem_catalog": {
            "current_formal_runner": _current_problem_catalog(root, manifests),
            "legacy_go_runner": _legacy_problem_catalog(root),
        },
        "manifest_inventory": manifests,
        "core_benchmarks": _core_benchmark_inventory(root),
        "algorithm_assets": {
            **_deduplicate_algorithms(algorithm_records),
            "records": algorithm_records,
        },
        "selector_pools": [selector_pool],
        "knowledge_assets": _knowledge_asset_inventory(root),
        "structural_boundaries": {
            "current_formal_runner_problem_count": len(RUNNABLE_PROBLEMS),
            "legacy_go_runner_problem_count": len(PROBLEM_SPECS),
            "per_instance_selector_problem_count": 1,
            "selector_ready_expert_count": len(selector_pool["expert_ids"]),
            "legacy_go_problems_are_not_current_formal_runner_problems": True,
            "cross_problem_best_codes_are_not_selector_registered": True,
        },
    }


def render_markdown(inventory: dict[str, Any]) -> str:
    lines = [
        "# Research Asset Inventory",
        "",
        "Generated by `scripts/research_asset_inventory.py`; do not edit counts manually.",
        "",
        "This is a reproducibility inventory, not a scientific ranking.",
        "",
        "## Current Formal Runner Problems",
        "",
        "| Problem | Target | Direction | Manifest occurrences |",
        "|---|---|---|---:|",
    ]
    for item in inventory["problem_catalog"]["current_formal_runner"]:
        lines.append(
            f"| `{item['problem_id']}` | `{item['target_function']}` | "
            f"{item['objective_direction']} | {item['manifest_occurrences']} |"
        )

    lines.extend(
        [
            "",
            "## Legacy Go Runner Problems",
            "",
            "| Problem | Language | Direction | Current formal runner |",
            "|---|---|---|---:|",
        ]
    )
    for item in inventory["problem_catalog"]["legacy_go_runner"]:
        lines.append(
            f"| `{item['problem_id']}` | {item['language']} | {item['objective_direction']} | "
            f"{'yes' if item['registered_in_current_formal_runner'] else 'no'} |"
        )

    lines.extend(
        [
            "",
            "## Algorithm Asset Records",
            "",
            f"- Records: {inventory['algorithm_assets']['record_count']}",
            (
                "- Unique computed code/file hashes: "
                f"{inventory['algorithm_assets']['unique_computed_code_hashes']}"
            ),
            "- RAG algorithm cards are counted separately and are not treated as verified algorithms.",
            "",
            "| Asset | Problem | Actor (raw) | Roles | Hash status | Selector pool |",
            "|---|---|---|---|---|---|",
        ]
    )
    for item in inventory["algorithm_assets"]["records"]:
        selector_pool = item["selector_pool_id"] or "-"
        lines.append(
            f"| `{item['asset_id']}` | `{item['problem_id']}` | `{item['actor_raw']}` | "
            f"{', '.join(item['declared_roles']) or '-'} | {item['code_hash_status']} | "
            f"`{selector_pool}` |"
        )

    lines.extend(
        [
            "",
            "## Selector Pools",
            "",
            "| Contract | Selector problem | Target problem | Experts | Features | Confirmation visible |",
            "|---|---|---|---:|---:|---:|",
        ]
    )
    for item in inventory["selector_pools"]:
        lines.append(
            f"| `{item['contract_id']}` | `{item['selector_problem_id']}` | "
            f"`{item['target_problem_id']}` | {len(item['expert_ids'])} | "
            f"{len(item['feature_order'])} | "
            f"{'yes' if item['confirmation_visible_during_evolution'] else 'no'} |"
        )

    lines.extend(
        [
            "",
            "## Evidence Boundaries",
            "",
            "- Only the four CVRP experts are registered in a per-instance selector pool.",
            "- Historical Go problems remain outside the current formal runner.",
            "- Cross-problem best-code files are experiment outputs, not selector-ready experts.",
            "- Duplicate code hashes are retained as provenance records and are not counted as new algorithms.",
            "",
        ]
    )
    return "\n".join(lines)


def write_inventory(root: Path, json_output: Path, markdown_output: Path) -> dict[str, Any]:
    inventory = build_inventory(root)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_output.write_text(render_markdown(inventory), encoding="utf-8")
    return inventory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN_OUTPUT)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    inventory = write_inventory(
        root,
        root / args.json_output,
        root / args.markdown_output,
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "current_problem_count": len(
                    inventory["problem_catalog"]["current_formal_runner"]
                ),
                "algorithm_asset_records": inventory["algorithm_assets"]["record_count"],
                "selector_pool_count": len(inventory["selector_pools"]),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
