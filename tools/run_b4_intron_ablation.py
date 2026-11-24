"""Measure the effect of removing four dead assignments from the M3.2 champion."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent_skill_loop.interface_design.blind_eval_m32 import _public_record
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver, ValidationReport, sha256_text
from agent_skill_loop.interface_design.planner import build_design_for_template
from agent_skill_loop.interface_design.runtime import evaluate_frozen_interface_solver
from agent_skill_loop.interface_design.session_baseline import load_dev_or_public_suite
from agent_skill_loop.interface_design.templates import get_template_spec
from agent_skill_loop.interface_design.validator import InterfaceValidator
from research_agent.contracts import atomic_write_json, atomic_write_text

M32_CHAMPION_CHECKPOINT = (
    REPO / "experiments/milestone3_2/runs/timeout_2000ms_s20261124/checkpoints/frozen_checkpoint_400.json"
)
M32_CHAMPION_ID = "ckpt_cand_8c4dfb41aa"
M32_CHAMPION_HOOK_SHA256 = "8c4dfb41aa5f96ff76b871ab910ade1d12cca457412941266644dca779180c28"
M32_PRUNED_CHAMPION_ID = f"{M32_CHAMPION_ID}_pruned"
_INTRONS = {
    7: "    rload = np.asarray(route_loads, dtype=np.float64)",
    8: "    rdist = np.asarray(route_dists, dtype=np.float64)",
    78: "    temp = 0.15 + 1.05 * diversify_w + 0.85 * st * (0.5 + 0.5 * exploit_w)",
    79: "    temp = float(np.clip(temp, 0.05, 2.0))",
}
EXTERNAL_CVRPLIB_SUITES = (
    ("cvrp_ext_cvrplib_abp_74", "heldout", "external_evaluation"),
    ("cvrp_ext_cvrplib_x_100", "heldout", "external_evaluation"),
)
_SUITES = (
    ("cvrp_dev_hetero_24", "dev_train", "diagnostic_interactive"),
    ("cvrp_select_multiscale_64", "selection", "selection_tuning"),
    *EXTERNAL_CVRPLIB_SUITES,
)
_DEADLINES_MS = (500.0, 2000.0)
_REPEATS = 3


def load_raw_m32_champion(checkpoint_path: Path = M32_CHAMPION_CHECKPOINT) -> dict[str, Any]:
    checkpoint = json.loads(Path(checkpoint_path).read_bytes())
    raw = checkpoint["frozen_solver"]
    _read_raw_champion(raw)
    return raw


def _read_raw_champion(raw_solver_dict: Mapping[str, Any]) -> FrozenInterfaceSolver:
    raw = FrozenInterfaceSolver.from_dict(raw_solver_dict)
    if raw.solver_id != M32_CHAMPION_ID or raw.hook_code_sha256 != M32_CHAMPION_HOOK_SHA256:
        raise ValueError("unexpected_m32_champion")
    if (raw.template_id, raw.template_version) != ("cvrp_ruin_recreate", "v1"):
        raise ValueError("unexpected_m32_champion_template")
    return raw


def build_pruned_m32_champion(raw_solver_dict: Mapping[str, Any]) -> dict[str, Any]:
    """Return a new manifest preserving every source byte outside four assignments."""
    raw = _read_raw_champion(raw_solver_dict)
    lines = raw.hook_code.splitlines(keepends=True)
    if any(lines[index - 1].rstrip("\r\n") != source for index, source in _INTRONS.items()):
        raise ValueError("unexpected_m32_champion_intron_layout")
    code = "".join(line for index, line in enumerate(lines, 1) if index not in _INTRONS)
    template = get_template_spec(raw.template_id, raw.template_version)
    return replace(
        raw,
        solver_id=M32_PRUNED_CHAMPION_ID,
        display_name=f"{raw.display_name} (dead assignments removed)",
        hook_code=code,
        hook_code_sha256=sha256_text(code),
        hook_specs=template.effective_hook_specs,
        hook_implementations={raw.hook_name: code},
        hook_hashes={},
        bundle_hash=None,
        hook_contract_sha256=None,
    ).to_dict()


def load_m32_champion_solver(solver_dict: Mapping[str, Any]) -> FrozenInterfaceSolver:
    """Verify the artifact before adapting its one hook to the v1 runtime schema."""
    if solver_dict.get("solver_id") != M32_PRUNED_CHAMPION_ID:
        return _read_raw_champion(solver_dict)
    solver = FrozenInterfaceSolver.from_dict(solver_dict)
    template = get_template_spec("cvrp_ruin_recreate", "v1")
    if (
        (solver.template_id, solver.template_version) != (template.template_id, template.template_version)
        or solver.hook_specs != template.effective_hook_specs
        or solver.bundle_hash is None
    ):
        raise ValueError("invalid_pruned_m32_champion_bundle")
    return replace(
        solver, hook_specs=template.hook_specs, hook_implementations={}, hook_hashes={},
        bundle_hash=None, hook_contract_sha256=None,
    )


def validate_frozen_solver(
    solver: FrozenInterfaceSolver,
    *,
    instance_time_budget_ms: float,
    allow_extended_numpy_whitelist: bool | None = None,
) -> ValidationReport:
    template = get_template_spec(solver.template_id, solver.template_version)
    if (
        template.template_source_sha256 != solver.template_source_sha256
        or template.hook_name != solver.hook_name or template.hook_specs != solver.hook_specs
        or template.problem_family != solver.problem_family
        or solver.postprocess_mode not in template.allowed_postprocess_modes
        or solver.protocol_id not in (None, template.effective_protocol_id)
    ):
        raise ValueError(f"invalid_frozen_solver_template_identity:{solver.solver_id}")
    design = build_design_for_template(
        solver.template_id, solver.template_version, postprocess_mode=solver.postprocess_mode,
    )
    design = replace(design, template_options=solver.template_options)
    validator = InterfaceValidator(
        instance_time_budget_ms=instance_time_budget_ms,
        allow_extended_numpy_whitelist=allow_extended_numpy_whitelist,
    )
    return validator.validate(
        design,
        hook_code_override=solver.hook_code,
        hook_implementations=solver.hook_implementations or None,
    )


def evaluate_public_frozen_solver(
    solver: FrozenInterfaceSolver,
    instance: Mapping[str, Any],
    suite: Mapping[str, Any],
    *,
    solve_deadline_ms: float,
) -> dict[str, Any]:
    return evaluate_frozen_interface_solver(
        solver, instance,
        distance_convention=suite["distance_convention"],
        vehicle_limit_policy=suite["vehicle_limit_policy"],
        solve_deadline_ms=solve_deadline_ms,
        enforce_wall_deadline=True,
    )


def _evaluate_pairs(
    solvers: Mapping[str, FrozenInterfaceSolver], suite: Mapping[str, Any], deadline_ms: float,
) -> list[dict[str, Any]]:
    rows = []
    for repeat in range(1, _REPEATS + 1):
        for index, instance in enumerate(suite["instances"]):
            pair: dict[str, Any] = {
                "instance_id": instance["instance_id"], "size": instance["size"], "repeat": repeat,
            }
            order = tuple(solvers) if (repeat + index) % 2 else tuple(reversed(solvers))
            for label in order:
                result = evaluate_public_frozen_solver(
                    solvers[label], instance, suite, solve_deadline_ms=deadline_ms,
                )
                code = result.get("error_code")
                if code in {"worker_protocol", "worker_crash", "worker_start_failed"}:
                    raise RuntimeError(f"b4_evaluator_failed:{label}:{code}")
                pair[label] = {
                    **_public_record(instance, result),
                    "exact_vehicle_count": result.get("exact_vehicle_count"),
                    "vehicle_target_available": instance.get("k_vehicles") is not None
                    or instance.get("max_vehicles") is not None,
                    "hook_ms": result.get("hook_ms"),
                }
            rows.append(pair)
    return rows


def _parity(pairs: Sequence[Mapping[str, Any]], eligibility: str) -> dict[str, Any]:
    diffs = [
        abs(pair["raw"]["objective"] - pair["pruned"]["objective"])
        for pair in pairs if pair["raw"][eligibility] and pair["pruned"][eligibility]
    ]
    return {
        "paired_count": len(diffs),
        "exact_parity_count": diffs.count(0.0),
        "max_abs_diff": max(diffs, default=None),
    }


def _outcomes(rows: Sequence[Mapping[str, Any]], *, free_fleet_with_lower_bound: bool) -> dict[str, Any]:
    targets = [row for row in rows if row["vehicle_target_available"]]
    target_matches = sum(row["feasible"] and row["exact_vehicle_count"] is True for row in targets)
    match_rate = target_matches / len(targets) if targets else None
    return {
        "completed_count": sum(row["completed"] for row in rows),
        "completion_rate": sum(row["completed"] for row in rows) / len(rows),
        "feasible_rate": sum(row["feasible"] for row in rows) / len(rows),
        "budget_exhausted_count": sum(row["budget_exhausted"] for row in rows),
        "vehicle_target_count": len(targets),
        "exact_k_rate": None if free_fleet_with_lower_bound else match_rate,
        "minimum_fleet_match_rate": match_rate if free_fleet_with_lower_bound else None,
    }


def _timing(pairs: Sequence[Mapping[str, Any]], field: str) -> dict[str, Any]:
    matched = [(p["raw"][field], p["pruned"][field]) for p in pairs
               if p["raw"][field] is not None and p["pruned"][field] is not None]
    result: dict[str, Any] = {"paired_count": len(matched)}
    for name, summarize in (("mean", statistics.mean), ("median", statistics.median)):
        raw = summarize(left for left, _ in matched) if matched else None
        pruned = summarize(right for _, right in matched) if matched else None
        result[name] = {"raw_ms": raw, "pruned_ms": pruned, "speedup": raw / pruned if pruned else None}
    return result


def _summarize(pairs: Sequence[Mapping[str, Any]], vehicle_policy: str) -> dict[str, Any]:
    by_size = defaultdict(list)
    for pair in pairs:
        by_size[pair["size"]].append(pair)
    return {
        "overall": {
            label: _outcomes(
                [pair[label] for pair in pairs], free_fleet_with_lower_bound=vehicle_policy == "free_fleet_min_k_lb",
            ) for label in ("raw", "pruned")
        },
        "objective_parity": _parity(pairs, "completed"),
        "raw_feasible_objective_parity": _parity(pairs, "feasible"),
        "by_size": {
            str(size): {field: _timing(group, field) for field in ("solve_ms", "hook_ms")}
            for size, group in sorted(by_size.items())
        },
    }


def _markdown(report: Mapping[str, Any]) -> str:
    def fmt(value: float | None) -> str:
        return "—" if value is None else f"{value:.4g}"

    lines = [
        "# B4 CVRP intron ablation", "",
        "Three paired repeats per instance and deadline. Speedups divide raw time by pruned time.",
        "Objective parity is measured on jointly completed runs, with feasible incumbents reported separately in JSON.",
    ]
    for suite_id, suite in report["suites"].items():
        lines.extend(("", f"## {suite_id}", "", f"Fleet policy `{suite['vehicle_limit_policy']}`."))
        for deadline, summary in suite["deadlines_ms"].items():
            parity = summary["objective_parity"]
            lines.extend((
                "", f"### {deadline} ms", "",
                f"Exact objective parity {parity['exact_parity_count']}/{parity['paired_count']}, "
                f"maximum absolute difference {fmt(parity['max_abs_diff'])}.", "",
                "| Solver | Completion rate | Feasible rate | Exact-k rate | Minimum-fleet match rate |",
                "| --- | ---: | ---: | ---: | ---: |",
            ))
            for label, row in summary["overall"].items():
                values = [fmt(row[key]) for key in (
                    "completion_rate", "feasible_rate", "exact_k_rate", "minimum_fleet_match_rate",
                )]
                lines.append("| " + " | ".join((label, *values)) + " |")
            lines.extend((
                "", "| Size | Metric | Raw mean ms | Pruned mean ms | Mean speedup | Raw median ms | Pruned median ms | Median speedup |",
                "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ))
            for size, timings in summary["by_size"].items():
                for field, timing in timings.items():
                    values = [fmt(timing[stat][key]) for stat in ("mean", "median")
                              for key in ("raw_ms", "pruned_ms", "speedup")]
                    lines.append("| " + " | ".join((size, field, *values)) + " |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=REPO / "experiments/milestone5")
    args = parser.parse_args(argv)
    raw = load_raw_m32_champion()
    manifests = {"raw": raw, "pruned": build_pruned_m32_champion(raw)}
    solvers = {label: load_m32_champion_solver(doc) for label, doc in manifests.items()}
    report: dict[str, Any] = {"schema_version": "m5-b4-intron-ablation/v1", "repeats": _REPEATS, "solvers": {}, "suites": {}}
    for label, solver in solvers.items():
        validation = validate_frozen_solver(solver, instance_time_budget_ms=2000.0)
        if not validation.passed:
            raise RuntimeError(f"b4_solver_validation_failed:{label}:{[f.error_code for f in validation.failures]}")
        report["solvers"][label] = {
            "solver_id": solver.solver_id, "hook_code_sha256": solver.hook_code_sha256,
            "bundle_hash": manifests[label].get("bundle_hash"), "validation_passed": validation.passed,
        }

    for suite_id, split, role in _SUITES:
        suite = load_dev_or_public_suite(suite_id, split=split, role=role)
        suite_report = {
            "split": split, "role": role, "instance_count": len(suite["instances"]),
            "vehicle_limit_policy": suite["vehicle_limit_policy"], "deadlines_ms": {},
        }
        for deadline in _DEADLINES_MS:
            print(f"Evaluating {suite_id} at {deadline:g} ms ({_REPEATS} paired repeats)", flush=True)
            pairs = _evaluate_pairs(solvers, suite, deadline)
            suite_report["deadlines_ms"][str(int(deadline))] = _summarize(pairs, suite["vehicle_limit_policy"])
        report["suites"][suite_id] = suite_report

    atomic_write_json(args.output_dir / "b4_intron_ablation.json", report)
    atomic_write_text(args.output_dir / "b4_intron_ablation.md", _markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
