"""CLI implementation for offline benchmark assets and contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .catalog import benchmark_profile, load_benchmark_registry
from .contracts import ExperimentManifest, FrozenSelection, PopulationSnapshot, sha256_json
from .harness import calibrate_differential, calibrate_upstream, evaluate_candidate, evaluate_candidate_set, evaluate_selection, load_suite
from .pilot import build_pilot_manifests
from .report import build_report


def _write(path: Path | None, payload: Any) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if path is None:
        print(text, end="")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def cmd_audit(args: Any) -> int:
    root = Path(__file__).resolve().parents[2]
    registry = load_benchmark_registry(Path(args.registry) if args.registry else None)
    findings: list[dict[str, Any]] = []
    for item in registry["benchmarks"]:
        manifest_paths = item.get("manifest_paths", {})
        manifest_hashes = item.get("manifests", {})
        for split, key in (("dev_train", "train_hash"), ("heldout", "test_hash")):
            target = root / "benchmarks" / "eohs_v1" / str(manifest_paths[split])
            actual = __import__("hashlib").sha256(target.read_bytes()).hexdigest()
            findings.append({"asset": split, "path": target.relative_to(root).as_posix(), "expected_sha256": manifest_hashes[key], "actual_sha256": actual, "status": "ok" if actual == manifest_hashes[key] else "mismatch"})
        reference_path = root / "benchmarks" / "eohs_v1" / str(manifest_paths.get("reference", ""))
        expected_reference = manifest_hashes.get("reference_hash")
        if not reference_path.is_file() or not expected_reference:
            findings.append({"asset": "reference", "path": reference_path.relative_to(root).as_posix(), "expected_sha256": expected_reference, "actual_sha256": None, "status": "missing"})
        else:
            actual = __import__("hashlib").sha256(reference_path.read_bytes()).hexdigest()
            findings.append({"asset": "reference", "path": reference_path.relative_to(root).as_posix(), "expected_sha256": expected_reference, "actual_sha256": actual, "status": "ok" if actual == expected_reference else "mismatch"})
    payload = {"schema_version": "algorithm-optimization-benchmark-audit/v1", "registry_sha256": sha256_json(registry), "assets": findings,
               "passed": all(item["status"] == "ok" for item in findings)}
    _write(Path(args.output) if args.output else None, payload)
    return 0 if payload["passed"] else 1


def cmd_calibrate(args: Any) -> int:
    suite = load_suite(Path(args.suite) if args.suite else None, benchmark_id=args.benchmark_id, profile=args.profile, split=args.split)
    gold = calibrate_upstream(suite)
    if args.gold:
        expected = json.loads(Path(args.gold).read_text(encoding="utf-8"))
        result = calibrate_differential(suite, expected)
        _write(Path(args.output) if args.output else None, result)
        return 0 if result["passed"] else 1
    _write(Path(args.output) if args.output else None, gold)
    return 0


def cmd_evaluate(args: Any) -> int:
    suite = load_suite(Path(args.suite) if args.suite else None, benchmark_id=args.benchmark_id, profile=args.profile, split=args.split)
    code = Path(args.code).read_text(encoding="utf-8")
    _benchmark, metric, _item = benchmark_profile(args.benchmark_id, args.profile)
    result = evaluate_candidate(code, suite, timeout=args.timeout, metric_spec=metric)
    _write(Path(args.output) if args.output else None, result)
    return 0 if result.get("valid") else 1


def cmd_evaluate_set(args: Any) -> int:
    suite = load_suite(Path(args.suite) if args.suite else None, benchmark_id=args.benchmark_id, profile=args.profile, split=args.split)
    candidates = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    _benchmark, metric, _item = benchmark_profile(args.benchmark_id, args.profile)
    result = evaluate_candidate_set(candidates, suite, timeout=args.timeout, metric_spec=metric)
    _write(Path(args.output) if args.output else None, result)
    return 0 if result.get("complete_instance_coverage") else 1


def cmd_evaluate_selection(args: Any) -> int:
    suite = load_suite(Path(args.suite) if args.suite else None, benchmark_id=args.benchmark_id, profile=args.profile, split=args.split)
    _benchmark, metric, _item = benchmark_profile(args.benchmark_id, args.profile)
    selection = FrozenSelection.from_dict(json.loads(Path(args.selection).read_text(encoding="utf-8")))
    result = evaluate_selection(selection, suite, timeout=args.timeout, metric_spec=metric)
    _write(Path(args.output) if args.output else None, result)
    return 0


def cmd_snapshot(args: Any) -> int:
    members = json.loads(Path(args.population).read_text(encoding="utf-8"))
    if isinstance(members, dict):
        members = members.get("members", members.get("population", []))
    snapshot = PopulationSnapshot.from_members(members, generation=args.generation, metric_spec_hash=args.metric_spec_hash,
                                               problem_spec_hash=args.problem_spec_hash, data_manifest_hash=args.data_manifest_hash,
                                               evaluator_hash=args.evaluator_hash)
    _write(Path(args.output) if args.output else None, {**snapshot.as_dict(), "content_hash": snapshot.content_hash})
    return 0


def cmd_freeze_selection(args: Any) -> int:
    entries: list[dict[str, Any]] = []
    if args.archive:
        payload = json.loads(Path(args.archive).read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = payload.get("entries", payload.get("archive", []))
        if not isinstance(payload, list):
            raise ValueError("archive_invalid")
        entries = [dict(item) for item in payload if isinstance(item, dict)]
    if args.kind != "final_population_set" and not args.archive:
        raise ValueError("selection_archive_required")
    snapshot = None
    if args.population_snapshot:
        snapshot = PopulationSnapshot.from_dict(
            json.loads(Path(args.population_snapshot).read_text(encoding="utf-8"))
        )
    from .archive import freeze_selection
    selection = freeze_selection(
        args.kind,
        entries,
        metric_spec_hash=args.metric_spec_hash,
        source_ref=args.source_ref,
        k=args.k,
        population_snapshot=snapshot,
    )
    _write(Path(args.output) if args.output else None, {**selection.as_dict(), "content_hash": selection.content_hash})
    return 0


def cmd_manifest(args: Any) -> int:
    payload = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("experiment_manifest_config_invalid")
    payload.pop("schema_version", None)
    payload.pop("manifest_version", None)
    payload.pop("experiment_manifest_sha256", None)
    manifest = ExperimentManifest(**payload)
    _write(Path(args.output) if args.output else None, {**manifest.as_dict(), "experiment_manifest_sha256": manifest.content_hash})
    return 0


def cmd_pilot_config(args: Any) -> int:
    payload = json.loads(Path(args.config).read_text(encoding="utf-8"))
    result = build_pilot_manifests(payload)
    _write(Path(args.output) if args.output else None, result)
    return 0


def cmd_report(args: Any) -> int:
    manifest_payload = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    if not isinstance(manifest_payload, dict):
        raise ValueError("experiment_manifest_invalid")
    for key in ("schema_version", "experiment_manifest_sha256"):
        manifest_payload.pop(key, None)
    manifest = ExperimentManifest(**manifest_payload)
    selection = FrozenSelection.from_dict(json.loads(Path(args.selection).read_text(encoding="utf-8")))
    metrics = json.loads(Path(args.metrics).read_text(encoding="utf-8"))
    budget = json.loads(Path(args.budget).read_text(encoding="utf-8"))
    test_result = None
    if args.test_result:
        test_result = json.loads(Path(args.test_result).read_text(encoding="utf-8"))
    if not isinstance(metrics, dict) or not isinstance(budget, dict):
        raise ValueError("benchmark_report_payload_invalid")
    result = build_report(
        manifest=manifest,
        selection=selection,
        metrics=metrics,
        budget=budget,
        source=args.source,
        test_result=test_result,
    )
    _write(Path(args.output) if args.output else None, result)
    return 0
