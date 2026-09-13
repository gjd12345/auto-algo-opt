"""Benchmark contracts and offline utilities for the v1.1 release line.

The benchmark package is deliberately independent of the provider and of the
official EoH process.  It owns immutable identities, deterministic population
selection, provenance records, and reporting facts; the Session runtime may
consume these records but never treats a report as control state.
"""

from .contracts import (
    ALLOWED_FROZEN_SELECTION_KINDS,
    ALLOWED_REFERENCE_KINDS,
    ALLOWED_ASSET_STATUSES,
    BenchmarkSpec,
    ExperimentManifest,
    FrozenSelection,
    MetricSpec,
    PopulationSnapshot,
    SeedSelection,
    evaluation_identity,
    sha256_json,
    sha256_text,
)
from .catalog import benchmark_profile, load_benchmark_registry, load_profile_suite
from .archive import ArchiveEntry, build_archive, freeze_selection
from .report import build_report
from .harness import calibrate_differential, calibrate_production, calibrate_upstream, evaluate_candidate, evaluate_candidate_set, evaluate_selection
from .pilot import PILOT_GROUPS, build_pilot_manifests

__all__ = [
    "ALLOWED_ASSET_STATUSES",
    "ALLOWED_FROZEN_SELECTION_KINDS",
    "ALLOWED_REFERENCE_KINDS",
    "BenchmarkSpec",
    "ArchiveEntry",
    "ExperimentManifest",
    "FrozenSelection",
    "MetricSpec",
    "PopulationSnapshot",
    "SeedSelection",
    "build_archive",
    "build_report",
    "benchmark_profile",
    "evaluation_identity",
    "load_benchmark_registry",
    "load_profile_suite",
    "sha256_json",
    "sha256_text",
    "freeze_selection",
    "calibrate_differential",
    "calibrate_production",
    "calibrate_upstream",
    "evaluate_candidate",
    "evaluate_candidate_set",
    "evaluate_selection",
    "PILOT_GROUPS",
    "build_pilot_manifests",
]
