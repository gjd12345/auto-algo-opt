"""Small deterministic report payload builder; human rendering is downstream."""

from __future__ import annotations

from typing import Any, Mapping

from .contracts import ExperimentManifest, FrozenSelection


def build_report(*, manifest: ExperimentManifest, selection: FrozenSelection,
                 metrics: Mapping[str, Any], budget: Mapping[str, Any], source: str = "artifact_reevaluated") -> dict[str, Any]:
    if source not in {"published_reported", "artifact_reevaluated", "search_rerun"}:
        raise ValueError("invalid_result_source")
    return {
        "schema_version": "algorithm-optimization-benchmark-report/v1",
        "experiment_manifest_sha256": manifest.content_hash,
        "selection_kind": selection.selection_kind,
        "selection_sha256": selection.content_hash,
        "result_source": source,
        "metrics": dict(metrics),
        "budget": dict(budget),
        "test_isolation": {"locked_before_test": selection.locked, "test_updates_training": False},
    }
