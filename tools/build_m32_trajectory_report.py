"""Build the self-contained M3.2 trajectory report from recorded artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sqlite3
import statistics
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent_skill_loop.interface_design.blind_eval import paired_bootstrap_comparison
from agent_skill_loop.interface_design.blind_eval_m3 import holm_bonferroni_adjust

SEEDS = (20261124, 20261125, 20261126)
BUDGETS = (36, 100, 200, 400)
TRACKS = ("curve", "model_routing", "l3b_dual_hook", "timeout_2000ms")
SIZES = ("n50", "n100", "n200")
COMPARATORS = {
    "cw_parallel_merge@500ms": 500,
    "cw_relocate_2opt@500ms": 500,
    "l3_ctrl@500ms": 500,
    "l3_ctrl@2000ms": 2000,
}
PAIR_COMPARATORS = ("l3_ctrl@2000ms", "cw_relocate_2opt@500ms")
M32_DIR = Path("experiments/milestone3_2")
OUTPUT = M32_DIR / "m32_evolution_trajectory.html"
HOOKS = ("score_ruin_nodes", "score_recreate_action")
MARKS = (10, 25, 100, 250, 500)
BLIND_KEY = re.compile(
    r"m32blind_(n50|n100|n200)_(uniform|clustered|mixed)_(centre|eccentric)_"
    r"(loose|tight)_(uniform|bimodal)-(\d{3})"
)
FORBIDDEN = re.compile(
    r"m32blind_|instance_ids?|sealed_seed_token|agent_skill_custody|"
    r"customer_coordinates|raw_coordinates|hook_code|solver_manifest_json|"
    r"[\\/]\.secrets[\\/]",
    re.IGNORECASE,
)
SOLVER_ID = re.compile(r"ckpt_cand_[0-9a-f]{10}|m32_[a-z0-9_]+_baseline_0")
MODELS = ("deepseek-v4.1-flash", "deepseek-v4-pro")
PURPOSES = ("planner", "reflection", "eoh_probe", "eoh_generation", "eoh_repair")
STATES = ("complete", "connectivity_failed", "http_error", "killed_unknown", "reserved", "sent")
ROUTES = ("single_model", "weak", "strong", "probe")
OUTCOMES = ("baseline_seed", "valid_candidate", "invalid_candidate", "eoh_skipped", "provider_failed", "probe", "pending")


def _number(value: Any) -> int | float | None:
    if value is None or value == "":
        return None
    if type(value) in (int, float) and math.isfinite(value):
        return value
    raise ValueError("Invalid numeric field")


def _tsv_number(value: str | None, convert: type[int] | type[float]) -> int | float | None:
    return _number(convert(value)) if value not in (None, "") else None


def _known(value: str | None, choices: Sequence[str]) -> str | None:
    if value is None:
        return None
    return value if value in choices else "other"


def _solver_id(value: Any) -> str:
    if not isinstance(value, str) or SOLVER_ID.fullmatch(value) is None:
        raise ValueError("Unexpected frozen solver identifier")
    return value


def _safe_js_json(payload: Any) -> str:
    """Encode JSON for an inline script, including script-tag and line separators."""
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        .replace("<", "\\u003c")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _input(root: Path, relative: Path) -> Path:
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root) or path != root / relative or not path.is_file():
        raise ValueError(f"Invalid artifact location: {relative.as_posix()}")
    return path


def _json(root: Path, relative: Path) -> dict[str, Any]:
    return json.loads(_input(root, relative).read_text(encoding="utf-8"))


def _cell(track: str, seed: int, budget: int = 400) -> str:
    return f"{seed}:checkpoint:{budget}" if track == "curve" else f"{seed}:control:{track}"


def _expected_cells() -> set[str]:
    return {
        _cell(track, seed, budget)
        for track in TRACKS for seed in SEEDS
        for budget in (BUDGETS if track == "curve" else (400,))
    }


@dataclass(frozen=True)
class BlindObservation:
    size: str
    spatial: str
    capacity: str
    depot: str
    ordinal: int
    objective: int | float | None
    reference: int | float | None
    solve_ms: int | float | None
    feasible: bool
    completed: bool
    exact_k: bool
    timeout: bool

    def penalized(self, *, strict: bool = False) -> int | float:
        if self.completed and self.objective is not None and (not strict or not self.timeout):
            return self.objective
        return 2 * self.reference if self.reference is not None else 1_000_000


def _blind_record(row: Mapping[str, Any]) -> BlindObservation:
    key = row.get("instance_id")
    match = BLIND_KEY.fullmatch(key) if isinstance(key, str) else None
    if match is None:
        raise ValueError("Unexpected blind evaluation key format")
    size, spatial, depot, capacity, _, ordinal = match.groups()
    objective = _number(row.get("objective"))
    feasible = row.get("feasible") is True and objective is not None
    return BlindObservation(
        size, spatial, capacity, depot, int(ordinal), objective,
        _number(row.get("reference_objective")), _number(row.get("solve_ms")),
        feasible, feasible and row.get("completed", True) is True,
        feasible and row.get("exact_k_feasible") is True,
        row.get("budget_exhausted") is True,
    )


def _blind_groups(doc: Mapping[str, Any]) -> dict[str, dict[str, BlindObservation]]:
    groups: dict[str, dict[str, BlindObservation]] = defaultdict(dict)

    def add(group: str, row: Mapping[str, Any]) -> None:
        observation = _blind_record(row)
        key = row["instance_id"]
        if key in groups[group]:
            raise ValueError(f"Duplicate blind evaluation key in {group}")
        groups[group][key] = observation

    expected = _expected_cells()
    for row in doc["records"]:
        group = row.get("cell")
        if group not in expected:
            raise ValueError("Unexpected evolved blind group")
        add(group, row)
    if set(doc["baseline_records"]) != set(COMPARATORS):
        raise ValueError("Unexpected comparator roster")
    for group, rows in doc["baseline_records"].items():
        for row in rows:
            add(group, row)
    if set(groups) != expected | COMPARATORS.keys():
        raise ValueError("Incomplete blind group coverage")
    reference = groups[PAIR_COMPARATORS[0]]
    if (
        {row.ordinal for row in reference.values()} != set(range(120))
        or any(sum(row.size == size for row in reference.values()) != 40 for size in SIZES)
    ):
        raise ValueError("Unexpected blind evaluation design coverage")
    for group, rows in groups.items():
        if rows.keys() != reference.keys():
            raise ValueError(f"Blind evaluation coverage mismatch in {group}")
    return groups


def _mean(values: Iterable[int | float | None]) -> float | None:
    finite = [value for value in values if value is not None]
    return statistics.fmean(finite) if finite else None


def _percentile(sorted_values: Sequence[int | float], fraction: float) -> float | None:
    if not sorted_values:
        return None
    position = fraction * (len(sorted_values) - 1)
    lower, upper = math.floor(position), math.ceil(position)
    return sorted_values[lower] + (position - lower) * (sorted_values[upper] - sorted_values[lower])


def _metrics(rows: Sequence[BlindObservation], deadline: int) -> dict[str, Any]:
    timed = sorted(row.solve_ms for row in rows if row.solve_ms is not None)
    counts = {
        "completed": sum(row.completed for row in rows),
        "within": sum(row.completed and not row.timeout for row in rows),
        "feasible": sum(row.feasible for row in rows),
        "exact": sum(row.exact_k for row in rows),
        "timeouts": sum(row.timeout for row in rows),
    }
    return {
        "n": len(rows), **counts,
        "raw": _mean(row.objective for row in rows if row.feasible),
        "completedMean": _mean(row.objective for row in rows if row.completed),
        "penalized": _mean(row.penalized() for row in rows),
        "strict": _mean(row.penalized(strict=True) for row in rows),
        "timed": len(timed),
        "under500": sum(value <= 500 for value in timed),
        "under2000": sum(value <= 2000 for value in timed),
        "solveWithin": sum(value <= deadline for value in timed),
        "solve": {f"p{p}": _percentile(timed, p / 100) for p in (10, 25, 50, 75, 90, 95)}
        | {"max": timed[-1] if timed else None},
    }


def _aggregate_groups(groups: Mapping[str, Mapping[str, BlindObservation]]) -> dict[str, Any]:
    result = {}
    for group, observations in groups.items():
        deadline = COMPARATORS.get(group, 2000 if group.endswith(":timeout_2000ms") else 500)
        rows = list(observations.values())
        slices: dict[str, list[BlindObservation]] = defaultdict(list)
        regimes: dict[tuple[str, str, str, str], list[BlindObservation]] = defaultdict(list)
        for row in rows:
            slices[row.size].append(row)
            regimes[row.size, row.spatial, row.capacity, row.depot].append(row)
        result[group] = {
            "deadline": deadline, "enforced": group not in COMPARATORS,
            "overall": _metrics(rows, deadline),
            "sizes": {size: _metrics(slices[size], deadline) for size in SIZES},
            "regimes": [
                {"size": size, "spatial": spatial, "capacity": capacity, "depot": depot,
                 **_metrics(subset, deadline)}
                for (size, spatial, capacity, depot), subset in sorted(regimes.items())
            ],
        }
    return result


def _common_completed(left: Sequence[BlindObservation], right: Sequence[BlindObservation]) -> dict[str, Any]:
    common = [(x.objective, y.objective) for x, y in zip(left, right, strict=True) if x.completed and y.completed]
    if not common:
        return {"commonN": 0, "commonGain": None}
    candidate, baseline = (math.fsum(values) for values in zip(*common))
    return {"commonN": len(common), "commonGain": 100 * (baseline - candidate) / baseline if baseline else None}


def _paired_rows(
    left: Mapping[str, BlindObservation], right: Mapping[str, BlindObservation]
) -> tuple[list[BlindObservation], list[BlindObservation]]:
    if not left or left.keys() != right.keys():
        raise ValueError("Paired comparison coverage mismatch")
    order = sorted(right, key=lambda key: right[key].ordinal)
    return [left[key] for key in order], [right[key] for key in order]


def _pair_summary(bootstrap: Mapping[str, Any]) -> dict[str, Any]:
    wtl = bootstrap["wtl_candidate_vs_baseline"]
    return {
        "n": int(bootstrap["n_instances"]), "gain": _number(bootstrap["rel_gain_vs_baseline_pct"]),
        "ci": [_number(value) for value in bootstrap["rel_gain_ci95_pct"]],
        "wtl": [int(wtl[key]) for key in ("wins", "ties", "losses")],
    }


def _statistics(
    published: Mapping[str, Any], groups: Mapping[str, Mapping[str, BlindObservation]]
) -> list[dict[str, Any]]:
    result = []
    for control in (*TRACKS[1:], "curve_400"):
        for seed in SEEDS:
            source_key = f"{control}_vs_curve_400_s{seed}" if control != "curve_400" else f"curve_400_vs_36_s{seed}"
            row = published[source_key]
            reference = "curve_36" if control == "curve_400" else "curve_400"
            candidate = _cell("curve" if control == "curve_400" else control, seed)
            left, right = _paired_rows(groups[candidate], groups[_cell("curve", seed, int(reference.split("_")[1]))])
            result.append({
                "family": "published", "seed": seed, "candidate": control, "reference": reference,
                **_pair_summary(row["bootstrap"]), **_common_completed(left, right),
                "p": _number(row["wilcoxon_p_two_sided"]), "pHolm": _number(row["p_holm_wilcoxon"]),
            })
    additional = []
    for comparator in PAIR_COMPARATORS:
        for seed in SEEDS:
            left, right = _paired_rows(groups[_cell("timeout_2000ms", seed)], groups[comparator])
            bootstrap = paired_bootstrap_comparison(
                [row.penalized() for row in left], [row.penalized() for row in right], n_boot=10_000, seed=seed,
            )
            additional.append({
                "family": "baseline", "seed": seed, "candidate": "timeout_2000ms", "reference": comparator,
                **_pair_summary(bootstrap), **_common_completed(left, right),
                "p": bootstrap["wilcoxon_signed_rank"]["p_two_sided"],
            })
    for row, adjusted in zip(additional, holm_bonferroni_adjust([row["p"] for row in additional]), strict=True):
        row["pHolm"] = adjusted
    return result + additional


def _usage(source: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _number(source.get(key)) for key in (
        "attempted_requests", "input_tokens", "output_tokens", "cached_tokens",
        "priced_cost_usd", "priced_attempts", "unpriced_attempts", "provider_elapsed_seconds",
    )}


def _hook_locs(solver: Mapping[str, Any]) -> dict[str, int]:
    implementations = solver.get("hook_implementations") or {solver["hook_name"]: solver["hook_code"]}
    if not implementations or set(implementations).difference(HOOKS):
        raise ValueError("Unexpected frozen hook names")
    return {key: len(code.splitlines()) for key, code in sorted(implementations.items())}


def _envelope(candidates: Sequence[Mapping[str, Any]]) -> list[list[int | float]]:
    result: list[list[int | float]] = []
    best = None
    for candidate in candidates:
        value = candidate["objective"]
        if candidate["eligible"] and value is not None and (best is None or value < best):
            result.append([candidate["ordinal"], value])
            best = value
    return result


def _run_db(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[sqlite3.Row]]:
    if any(path.with_name(path.name + suffix).exists() for suffix in ("-wal", "-shm", "-journal")):
        raise ValueError(f"Run ledger must be closed and checkpointed: {path.parent.name}")
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
        db.row_factory = sqlite3.Row
        candidates = [
            {"ordinal": row["global_ordinal"], "outcome": _known(row["generation_status"], OUTCOMES),
             "eligible": row["eligible"] == 1, "objective": _number(row["dev_penalized_mean"]),
             "completion": _number(row["dev_completion_rate"]), "feasible": row["dev_all_feasible"] == 1}
            for row in db.execute("""
                SELECT global_ordinal, generation_status, eligible, dev_penalized_mean,
                       dev_completion_rate, dev_all_feasible
                FROM candidate_provenance ORDER BY global_ordinal, attempt_token
            """)
        ]
        requests = [
            {"ordinal": row["idx"], "purpose": _known(row["purpose"], PURPOSES),
             "state": _known(row["state"], STATES), "http": _number(row["status"]),
             "error": _known(row["error_code"], ("provider_connectivity_or_protocol_error", "request_deadline")),
             "retry": _number(row["retry_index"]), "requested": _known(row["requested_model"], MODELS),
             "served": _known(row["served_model"], MODELS), "route": _known(row["route_role"], ROUTES),
             "logical": _number(row["logical_ordinal"]), "outcome": _known(row["generation_status"], OUTCOMES)}
            for row in db.execute("""
                SELECT b.idx, b.purpose, b.state, b.status, b.error_code, b.retry_index,
                       b.requested_model, b.served_model, b.logical_ordinal,
                       r.route_role, p.generation_status
                FROM budget_requests b
                LEFT JOIN candidate_provenance p ON p.run_id = b.run_id AND p.physical_request_id = b.request_id
                LEFT JOIN routing_logical_calls r ON r.run_id = b.run_id AND r.logical_call_id = b.logical_call_id
                ORDER BY b.idx
            """)
        ]
        seals = list(db.execute("""
            SELECT ckpt_budget, state, settled_through_ordinal, winner_source_ordinal
            FROM milestone_checkpoints ORDER BY ckpt_budget
        """))
    if [request["ordinal"] for request in requests] != list(range(1, 401)):
        raise ValueError(f"Unexpected physical request coverage: {path.parent.name}")
    return candidates, requests, seals


def _rounds(path: Path, summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = []
    previous = 0
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    for row, recorded in zip(rows, summary["round_summaries"], strict=True):
        round_id, cutoff = int(row["round_id"]), int(row["requests_used_total"])
        if (round_id, cutoff) != (int(recorded["round_id"]), int(recorded["requests_used_total"])) or cutoff < previous:
            raise ValueError("Round cutoff disagrees with research summary")
        result.append({
            "round": round_id, "start": previous + 1, "end": cutoff,
            "objective": _tsv_number(row.get("best_objective"), float),
            "delta": _tsv_number(row.get("delta_vs_prev"), float),
            "outer": _tsv_number(row.get("outer_requests_round"), int),
            "inner": _tsv_number(row.get("inner_requests_round"), int),
            "supported": _tsv_number(row.get("hypotheses_supported"), int),
            "refuted": _tsv_number(row.get("hypotheses_refuted"), int),
        })
        previous = cutoff
    return result


def _run(root: Path, track: str, seed: int, metadata: Mapping[str, Any]) -> dict[str, Any]:
    relative = M32_DIR / "runs" / f"{track}_s{seed}"
    candidates, requests, db_seals = _run_db(_input(root, relative / "agent_budget.sqlite3"))
    expected = BUDGETS if track == "curve" else (400,)
    if tuple(row["ckpt_budget"] for row in db_seals) != expected:
        raise ValueError(f"Unexpected seal coverage: {track} s{seed}")
    summary = _json(root, relative / "research_summary.json")
    rounds = _rounds(_input(root, relative / "results.tsv"), summary)
    checkpoints = []
    for record in db_seals:
        budget = record["ckpt_budget"]
        cell = _cell(track, seed, budget)
        frozen = _json(root, relative / "checkpoints" / f"frozen_checkpoint_{budget}.json")
        lock = metadata[cell]
        ordinal = frozen.get("winner_source_ordinal")
        objective = _number(frozen.get("best_dev_objective"))
        if (
            record["state"] != "sealed" or record["settled_through_ordinal"] != budget
            or frozen["checkpoint_budget"] != budget or frozen["settled_through_ordinal"] != budget
            or ordinal != record["winner_source_ordinal"] or ordinal != lock["winner_source_ordinal"]
            or objective != lock["best_dev_objective"] or frozen["usage_cutoff"] != lock["usage_cutoff"]
            or frozen["wall_elapsed_seconds_at_seal"] != lock["wall_elapsed_seconds_at_seal"]
        ):
            raise ValueError(f"Seal metadata mismatch: {cell}")
        if type(ordinal) is not int or not 0 <= ordinal <= budget or not any(
            row["ordinal"] == ordinal and row["objective"] == objective and row["eligible"] for row in candidates
        ):
            raise ValueError(f"Missing eligible checkpoint winner: {cell}")
        solver = frozen["frozen_solver"]
        checkpoints.append({
            "budget": budget, "ordinal": ordinal, "objective": objective,
            "solver": _solver_id(solver["solver_id"]), "hooks": _hook_locs(solver),
            "wall": _number(lock["wall_elapsed_seconds_at_seal"]), "usage": _usage(lock["usage_cutoff"]),
        })
    terminal = checkpoints[-1]["usage"]
    if (
        terminal["attempted_requests"] != len(requests)
        or terminal["attempted_requests"] != summary["budget_summary"]["attempted_requests"]
        or terminal["priced_cost_usd"] != summary["cost_summary"]["priced_cost_usd"]
    ):
        raise ValueError(f"Terminal usage mismatch: {track} s{seed}")
    return {
        "track": track, "seed": seed, "candidates": candidates, "envelope": _envelope(candidates),
        "requests": requests, "rounds": rounds, "checkpoints": checkpoints,
    }


def _operator_data(source: Mapping[str, Any], runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for run in runs:
        track, seed = run["track"], run["seed"]
        group = _cell(track, seed)
        row = source[group.replace(":", "_")]
        terminal = run["checkpoints"][-1]
        solver = _solver_id(row["solver_id"])
        hook_stats = row["hooks_ast"]
        locs = {name: int(stats["loc"]) for name, stats in hook_stats.items()}
        if solver != terminal["solver"] or locs != terminal["hooks"]:
            raise ValueError(f"M4 solver or hook LOC mismatch: {group}")
        preview = row["select_16_preview"]
        result.append({
            "group": group, "track": track, "seed": seed, "solver": solver, "hooks": locs,
            "ops": {key: sorted(set(stats["binary_ops"]) & {
                "Add", "BitAnd", "BitOr", "BitXor", "Div", "FloorDiv", "LShift", "Mod", "Mult", "Pow", "RShift", "Sub",
            }) for key, stats in hook_stats.items()},
            "valid": int(preview["valid_count"]), "mean": _number(preview["mean_tour_length"]),
            "anytime": [[ms, _number(preview["anytime_curve_means"].get(str(ms)))] for ms in MARKS],
        })
    return result


def _reconcile(source: Mapping[str, Any], aggregates: Mapping[str, Any]) -> None:
    published = dict(source["baseline_comparators"])
    for budget in BUDGETS:
        for seed in SEEDS:
            published[_cell("curve", seed, budget)] = source["scaling_curve"][str(budget)]["per_seed"][str(seed)]
    for track in TRACKS[1:]:
        for seed in SEEDS:
            published[_cell(track, seed)] = source["single_factor_controls"][track]["per_seed"][str(seed)]
    fields = {
        "instance_count": "n", "completed_count": "completed", "within_deadline_completed_count": "within",
        "feasible_count": "feasible", "exact_k_feasible_count": "exact", "timeout_count": "timeouts",
        "valid_only_mean_objective": "raw", "completed_only_mean_objective": "completedMean",
        "penalized_mean_objective": "penalized", "strict_deadline_penalized_mean_objective": "strict",
    }
    for group, row in published.items():
        for original, key in fields.items():
            expected, actual = row[original], aggregates[group]["overall"][key]
            if expected is None or actual is None:
                equal = expected is actual
            else:
                equal = math.isclose(expected, actual, rel_tol=0, abs_tol=1e-6)
            if not equal:
                raise ValueError(f"Published {original} disagrees with blind aggregate: {group}")


def build_payload(root: Path = REPO) -> dict[str, Any]:
    root = root.resolve()
    scaling = _json(root, M32_DIR / "m32_scaling_report.json")
    roster = _json(root, M32_DIR / "m32_roster_lock_bundle.json")
    blind = _json(root, M32_DIR / "blind_120_eval" / "m32_blind_evaluation.json")
    if (
        scaling.get("schema_version") != "m32-scaling-report/v1"
        or roster.get("schema_version") != "m32-roster-lock-bundle/v1"
        or blind.get("schema_version") != "m32-blind-evaluation/v1"
        or scaling.get("suite_id") != blind.get("suite_id")
        or any(blind.get(key) != roster.get(key) for key in ("protocol_sha256", "roster_lock_sha256"))
    ):
        raise ValueError("Inconsistent M3.2 artifact schema or study identity")
    metadata = roster["checkpoint_metadata"]
    expected = _expected_cells()
    if set(metadata) != expected or set(roster["snapshot_paths"]) != expected or roster["missing_cells"] or blind["missing_cells"]:
        raise ValueError("Incomplete M3.2 roster lock")
    runs = [_run(root, track, seed, metadata) for track in TRACKS for seed in SEEDS]
    terminals = [run["checkpoints"][-1]["usage"] for run in runs]
    groups = _blind_groups(blind)
    aggregates = _aggregate_groups(groups)
    _reconcile(scaling, aggregates)
    stats = _statistics(scaling["per_seed_paired_hypothesis_tests"], groups)
    operators = _operator_data(_json(root, Path("experiments/milestone4/m4_m32_operator_dissection.json")), runs)
    return {
        "version": 1, "seeds": list(SEEDS), "budgets": list(BUDGETS), "tracks": list(TRACKS),
        "comparators": list(COMPARATORS), "runs": runs, "blind": aggregates,
        "stats": stats, "operators": operators,
        "kpis": {
            "locked": len(metadata), "expected": len(expected),
            "requests": sum(row["attempted_requests"] for row in terminals),
            "priced": sum(row["priced_attempts"] for row in terminals),
            "unpriced": sum(row["unpriced_attempts"] for row in terminals),
            "cost": float(sum(Decimal(str(row["priced_cost_usd"])) for row in terminals if row["priced_cost_usd"] is not None)),
        },
    }


PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>M3.2 算法演化轨迹</title>
<style>
:root{color-scheme:light;--ink:#142740;--muted:#52657b;--line:#dbe4ef;--wash:#f3f7fc;--paper:#fff;
 --blue:#165dff;--green:#008c37;--red:#be2e31;--orange:#c15100;--gold:#ffce55;
 font:15px/1.55 "Segoe UI","Microsoft YaHei UI","PingFang SC",sans-serif;color:var(--ink);background:var(--wash)}
*{box-sizing:border-box}body{margin:0}header,main,footer,.nav-inner{width:min(1320px,calc(100% - 48px));margin:auto}
header{padding:33px 0 20px}h1,h2,h3,p{margin:0}h1{font-size:clamp(30px,5vw,50px);line-height:1.14;letter-spacing:-.035em}
h2{font-size:clamp(22px,3vw,29px);line-height:1.25}h3{font-size:17px}p{max-width:85ch}.muted,small{color:var(--muted)}
.executive{margin-top:15px;font-size:16px}.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:var(--line);
 border:1px solid var(--line);border-radius:8px;overflow:hidden;margin-top:22px}
.kpi{padding:13px 16px;background:var(--paper)}.kpi strong{display:block;font-size:clamp(18px,3vw,30px);line-height:1.3;font-variant-numeric:tabular-nums;color:#15396c}
.kpi span{display:block;color:var(--muted);font-size:13px}.nav{position:sticky;top:0;z-index:4;background:#edf3fa;border-block:1px solid var(--line)}
.nav-inner{display:flex;gap:19px;overflow:auto}.nav a{white-space:nowrap;padding:10px 0;color:#1d4b8c;font-weight:650;text-decoration:none}
.nav a:hover{text-decoration:underline}main{display:grid;gap:20px;margin-block:22px 30px}section{scroll-margin-top:60px;background:var(--paper);
 border:1px solid var(--line);border-radius:9px;padding:clamp(14px,3vw,26px)}.section-head{margin-bottom:13px;border-left:3px solid var(--blue);padding-left:11px}
.section-head p{margin-top:5px}.controls{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:end;margin:12px 0}.controls label{display:grid;gap:3px;color:var(--muted);font-size:13px}
select,button{font:inherit;color:var(--ink);background:#fff;border:1px solid #a9bbd2;border-radius:5px;padding:5px 9px}
select{min-width:118px;max-width:100%}button{cursor:pointer}button:hover{background:#eaf2ff}button[aria-pressed="true"]{background:#dceaff;border-color:var(--blue);color:#153d8c}
:focus-visible{outline:2px solid #165dff;outline-offset:2px}.chart{width:100%;overflow:auto}.chart svg{display:block;width:100%;height:auto;min-width:480px;overflow:hidden}
.axis{fill:var(--muted);font-size:12px}.chart-label{fill:var(--ink);font-size:13px;font-weight:600}.grid{stroke:#dfe7f1;stroke-width:1;vector-effect:non-scaling-stroke}
.mark{cursor:default}.mark:focus{outline:none;stroke:#152941;stroke-width:2.2}.legend{display:flex;gap:4px 16px;flex-wrap:wrap;margin:5px 0 9px;color:var(--muted);font-size:13px}
.legend i{display:inline-block;width:11px;height:8px;border-radius:2px;margin-right:5px}.split{display:grid;grid-template-columns:1fr 1fr;gap:15px}.sub{border-top:1px solid var(--line);padding-top:12px;margin-top:12px;min-width:0}
.table-wrap{overflow:auto;margin-top:8px}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;font-size:13px;text-align:left}
th,td{padding:5px 9px;border-bottom:1px solid var(--line);white-space:nowrap}thead th{background:#edf3fa;color:#365477}tbody tr:hover,tbody tr.selected{background:#eef5ff}
td button{font-size:12px;padding:2px 7px}.heat td{text-align:center;font-weight:650}.heat small{display:block;font-weight:400}.heat th{text-align:center}
.operator{padding:12px 14px;border:1px solid var(--line);border-radius:6px;background:#f8fbff}.operator p{margin-top:5px}.solver{font-family:Consolas,monospace;font-size:13px;color:#38547a}
#tip{position:fixed;z-index:10;pointer-events:none;max-width:calc(100vw - 16px);max-height:calc(100vh - 16px);overflow:hidden;
 background:#11253d;color:#fff;border:1px solid #263b55;border-radius:6px;padding:8px 11px;white-space:pre-line;overflow-wrap:anywhere;font-size:12px;box-shadow:0 3px 12px #13294540}
footer{padding-bottom:24px;font-size:13px}.note{margin:.35em 0 .45em;font-size:13px;color:var(--muted)}
@media(max-width:800px){.split{grid-template-columns:1fr}.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}header,main,footer,.nav-inner{width:calc(100% - 24px)}}
</style>
</head>
<body>
<header>
  <h1>M3.2 算法演化轨迹</h1>
  <p id="executive" class="executive"></p>
  <div id="kpis" class="kpis" aria-label="研究概览"></div>
</header>
<nav class="nav" aria-label="报告视图"><div class="nav-inner">
  <a href="#trajectory">搜索轨迹</a><a href="#scaling">扩展与延迟</a><a href="#paired">配对统计</a><a href="#operators">算子解剖</a>
</div></nav>
<main>
<section id="trajectory">
  <div class="section-head"><h2>开发集搜索轨迹</h2><p class="muted">请求序号 0–400 · 星标标出封存赢家出现的请求位置。</p></div>
  <div class="controls"><label>实验轨道<select id="dev-track"></select></label><label>搜索种子<select id="dev-seed"></select></label>
    <button id="compare-seeds" type="button" aria-pressed="false">全部对比 / Compare Seeds</button></div>
  <div id="dev-legend" class="legend"></div><div id="dev-chart" class="chart"></div>
  <div class="sub"><h3>请求流水</h3><div id="lane-legend" class="legend"></div><div id="dev-lanes" class="chart"></div></div>
  <div class="sub"><h3>轮次摘要</h3><p class="note">选择轮次以突出显示对应的请求区间。</p><div id="rounds" class="table-wrap"></div></div>
</section>
<section id="scaling">
  <div class="section-head"><h2>扩展曲线与延迟瓶颈</h2><p class="muted">并列查看预算、控制轨道和确定性求解器。未强制截停的对照以虚线标记。</p></div>
  <div class="controls"><label>指标<select id="metric"></select></label><label>实例规模<select id="size"></select></label></div>
  <div id="metric-note" class="note"></div><div id="scaling-chart" class="chart"></div>
  <div class="sub"><h3>求解时延与结构分层</h3>
    <div class="controls"><label>搜索种子<select id="slice-seed"></select></label><label>待比较方案<select id="slice-candidate"></select></label>
      <label>参考方案<select id="slice-reference"></select></label></div>
    <p class="note">线段为 p10–p95，粗条为 p25–p75，圆点为 p50，短刻线标出 p90 与最大值。求解时延按记录值计算，超时按实验标记计数。</p>
    <div id="latency" class="chart"></div>
    <h3>结构差值热图</h3><p class="note">每格显示方案减参考的差值与配对样本数。色深表示差值大小，括号内为样本数。</p><div id="heat" class="table-wrap"></div>
  </div>
  <details class="sub"><summary>查看所选规模及种子的精确指标</summary><div id="blind-detail" class="table-wrap"></div></details>
</section>
<section id="paired">
  <div class="section-head"><h2>配对统计</h2><p class="muted">正值表示候选成本下降。每行在同一组盲测实例上配对，按种子报告。</p></div>
  <div class="controls"><label>比较范围<select id="pair-family"></select></label></div>
  <div id="forest" class="chart"></div>
  <p class="note">区间为 10,000 次配对 Bootstrap 的 95% 区间。Holm 校正分别沿用已发布的 12 项比较和新增的 6 项对照比较。共同完成项以原始目标值重算。</p>
  <div id="pair-table" class="table-wrap"></div>
</section>
<section id="operators">
  <div class="section-head"><h2>M4 算子解剖</h2><p class="muted">随时间改善曲线来自 select_16 预览。代码行数散点使用盲测 n=200 的求解时延。</p></div>
  <div class="controls"><label>算子轨道<select id="operator-track"></select></label></div>
  <div id="operator-legend" class="legend"></div>
  <div class="split"><div><h3>select_16 随时间改善</h3><div id="anytime" class="chart"></div></div>
  <div><h3>Hook 行数与 n=200 时延</h3><div id="operator-scatter" class="chart"></div></div></div>
  <div class="split sub" id="operator-cards"></div>
</section>
</main>
<footer class="muted"><details><summary>数据来源与统计口径</summary><p>
M3.2 扩展报告、封存名册、盲测评估汇总、运行账本和轮次结果，以及 M4 算子解剖报告。确定性对照保留完整求解轨迹，超时仍以各自时限记录。时延分位数使用排序位置的线性插值。跨种子曲线显示每个种子的指标与可用种子的均值。</p></details></footer>
<div id="tip" role="tooltip" hidden></div>
<script type="application/json" id="m32-data">__REPORT_DATA__</script>
<script id="m32-app">__REPORT_APP__</script>
</body>
</html>
"""


APP = r"""
'use strict';
const $ = id => document.getElementById(id);
const data = JSON.parse($('m32-data').textContent);
const ns = 'http://www.w3.org/2000/svg';
const tracks = {curve:'主曲线',model_routing:'模型路由',l3b_dual_hook:'双 Hook',timeout_2000ms:'2000 ms 控制'};
const seeds = ['#165dff','#008c37','#a749a0'];
const trackColors = {curve:'#165dff',model_routing:'#c15100',l3b_dual_hook:'#a749a0',timeout_2000ms:'#008c37'};
const sizes = ['n50','n100','n200'];
const metricLabels = {penalized:'惩罚均值',raw:'原始均值',exact:'Exact-k 达成率',timeouts:'超时数'};
const labelMap = {uniform:'均匀',clustered:'聚簇',mixed:'混合',loose:'宽松',tight:'紧张',centre:'中心',eccentric:'偏心'};
const categories = {
  valid_candidate:['#008c37','有效候选'],invalid_candidate:['#f53f3f','无效候选'],eoh_skipped:['#ff7d00','跳过'],
  provider_failed:['#a749a0','生成失败'],probe:['#93a4bd','探针'],pending:['#c4cbd4','待结算'],
  complete:['#bad6fa','请求完成'],connectivity_failed:['#f53f3f','连接失败'],http_error:['#ff7d00','HTTP 错误'],
  killed_unknown:['#a749a0','请求期限触发'],reserved:['#c4cbd4','已预留'],sent:['#c4cbd4','已发送'],
  strong:['#165dff','强模型'],weak:['#9bbdff','轻量模型'],single_model:['#607f9d','单模型'],other:['#e3eaf3','其他']
};
const fmt = (v, digits=2) => v == null ? '—' : Number(v).toLocaleString('zh-CN',{maximumFractionDigits:digits});
const fixed = (v, digits=2) => v == null ? '—' : Number(v).toFixed(digits);
const signed = (v, digits=2) => v == null ? '—' : `${v > 0 ? '+' : ''}${fixed(v, digits)}`;
const pct = (count,n) => n ? 100 * count / n : null;
const avg = values => values.length ? values.reduce((sum,v) => sum + v,0) / values.length : null;
const cell = (track,seed,budget=400) => track === 'curve' ? `${seed}:checkpoint:${budget}` : `${seed}:control:${track}`;
const trackName = track => tracks[track] || track;
const runColor = seed => seeds[data.seeds.indexOf(seed)];
const sizeName = size => size === 'overall' ? '全部规模' : `n=${size.slice(1)}`;
const pValue = value => value == null ? '—' : value === 0 ? '<5e-9' : Number(value).toExponential(2);
const groupSpecs = [...data.budgets.map(b => [`curve_${b}`,`B=${b}`]), ...data.tracks.slice(1).map(t => [t,trackName(t)])];
const groupName = key => groupSpecs.find(([id]) => id === key)?.[1] || key;
const specCell = (key,seed) => key.startsWith('curve_') ? cell('curve',seed,Number(key.slice(6))) : cell(key,seed);
const subset = (group,size) => size === 'overall' ? group.overall : group.sizes[size];
const metricValue = (m,key) => key === 'exact' ? pct(m.exact,m.n) : m[key];
const label = (key) => categories[key]?.[1] ?? (key == null ? '—' : key);

function html(tag,text,attrs={}) {
  const el = document.createElement(tag);
  if (text != null) el.textContent = text;
  Object.entries(attrs).forEach(([key,value]) => el.setAttribute(key,value));
  return el;
}
function svg(parent,tag,attrs={},text=null) {
  const el = document.createElementNS(ns,tag);
  Object.entries(attrs).forEach(([key,value]) => el.setAttribute(key,value));
  if (text != null) el.textContent = text;
  parent.append(el);
  return el;
}
function options(id,choices,value) {
  $(id).replaceChildren(...choices.map(([id,label]) => html('option',label,{value:id})));
  if (value != null) $(id).value = value;
}
function chart(id,w,h,title) {
  const container = $(id);
  container.replaceChildren();
  return svg(container,'svg',{viewBox:`0 0 ${w} ${h}`,role:'group','aria-label':title});
}
function legend(id,items) {
  $(id).replaceChildren(...items.map(([color,text]) => {
    const chip = html('span');
    const swatch = html('i');
    swatch.style.backgroundColor = color;
    chip.append(swatch,document.createTextNode(text));
    return chip;
  }));
}
function table(id,columns,rows) {
  const tbl = html('table');
  const head = tbl.createTHead().insertRow();
  for (const column of columns) head.append(html('th',column,{scope:'col'}));
  const body = tbl.createTBody();
  for (const values of rows) {
    const row = body.insertRow();
    for (const value of values) {
      const td = row.insertCell();
      if (value instanceof Node) td.append(value);
      else td.textContent = value;
    }
  }
  $(id).replaceChildren(tbl);
  return tbl;
}
function showTip(text,x,y) {
  const tip = $('tip');
  tip.textContent = text;
  tip.hidden = false;
  const {width,height} = tip.getBoundingClientRect();
  tip.style.left = `${Math.max(8,Math.min(x+13,window.innerWidth-width-8))}px`;
  tip.style.top = `${Math.max(8,Math.min(y+13,window.innerHeight-height-8))}px`;
}
function hideTip() { $('tip').hidden = true; }
function hover(mark,text,focusable=true) {
  mark.classList.add('mark');
  mark.addEventListener('pointerenter',e => showTip(text,e.clientX,e.clientY));
  mark.addEventListener('pointermove',e => showTip(text,e.clientX,e.clientY));
  mark.addEventListener('pointerleave',hideTip);
  if (focusable) {
    mark.setAttribute('tabindex','0');
    mark.setAttribute('aria-label',text.replaceAll('\n',' · '));
    mark.addEventListener('focus',() => {
      const r = mark.getBoundingClientRect();
      showTip(text,r.left+r.width/2,r.bottom);
    });
    mark.addEventListener('blur',hideTip);
  }
  return mark;
}
function line(parent,x1,y1,x2,y2,attrs={}) { return svg(parent,'line',{x1,y1,x2,y2,...attrs}); }
function text(parent,x,y,value,attrs={}) { return svg(parent,'text',{x,y,class:'axis',...attrs},value); }
function scale(d0,d1,r0,r1) { return v => r0+(v-d0)/(d1-d0)*(r1-r0); }
function extent(values,pad=.08) {
  const good = values.filter(Number.isFinite);
  if (!good.length) return [0,1];
  const lo = Math.min(...good), hi = Math.max(...good);
  const gap = (hi-lo || Math.max(Math.abs(lo)*.1,1))*pad;
  return [lo-gap,hi+gap];
}
function ticks(lo,hi,n=4) { return Array.from({length:n+1},(_,i) => lo + (hi-lo)*i/n); }
function yGrid(view,y,values,left,right,formatter=fmt) {
  for (const value of values) {
    line(view,left,y(value),right,y(value),{class:'grid'});
    text(view,left-8,y(value)+4,formatter(value),{'text-anchor':'end'});
  }
}
function curve(view,points,x,y,attrs={},step=false) {
  let d = '', active = false;
  for (const [a,b] of points) {
    if (b == null) { active = false; continue; }
    d += !active ? `M${x(a)},${y(b)}` : step ? `H${x(a)}V${y(b)}` : `L${x(a)},${y(b)}`;
    active = true;
  }
  if (d) svg(view,'path',{d,fill:'none','stroke-width':2,...attrs});
}
function star(view,x,y) {
  const points = Array.from({length:10},(_,i) => {
    const angle = i*Math.PI/5 - Math.PI/2, radius = i%2 ? 4.5 : 10;
    return `${x+Math.cos(angle)*radius},${y+Math.sin(angle)*radius}`;
  }).join(' ');
  return svg(view,'polygon',{points,fill:'#ffce55',stroke:'#8c5600','stroke-width':1.25});
}

function overview() {
  const k = data.kpis;
  const main = data.seeds.map(seed => data.blind[cell('curve',seed)].sizes.n200);
  const long = data.seeds.map(seed => data.blind[cell('timeout_2000ms',seed)].overall);
  const comparison = data.stats.filter(row => row.reference === 'l3_ctrl@2000ms');
  const wins = comparison.filter(row => row.gain > 0 && row.pHolm < .05).length;
  const small = ['n50','n100'].every(size => data.seeds.every(seed => {
    const m = data.blind[cell('curve',seed)].sizes[size];
    return m.completed === m.n;
  }));
  $('executive').textContent = `B=400 主曲线在 n=50、100 ${small ? '全部完成' : '存在未完成项'}。n=200 超时数按种子为 ${main.map(m => `${m.timeouts}/${m.n}`).join('、')}。2000 ms 控制在 ${long.filter(m => m.timeouts === 0).length}/${long.length} 个种子无超时，相对 l3_ctrl@2000ms 在 ${wins}/${comparison.length} 个种子上显著降低成本（Holm 校正）。`;
  const items = [[`${k.locked}/${k.expected}`,'封存评估单元'],[fmt(k.requests,0),'终点请求数'],
    [`$${fixed(k.cost,4)}`,`已计价用量 · ${fmt(k.unpriced,0)} 次未计价`],[`${wins}/${comparison.length}`,'2000 ms 对照显著胜出种子']];
  for (const [value,caption] of items) {
    const card = html('div',null,{class:'kpi'});
    card.append(html('strong',value),html('span',caption));
    $('kpis').append(card);
  }
}

const seedOptions = data.seeds.map(seed => [seed,`s${seed}`]);
const trackOptions = data.tracks.map(track => [track,trackName(track)]);
const devLeft = 130, devRight = 1000;
let selectedRound = null;
let compareSeeds = false;
function activeRuns() {
  return data.runs.filter(run => run.track === $('dev-track').value && (compareSeeds || run.seed === Number($('dev-seed').value)));
}
function checkpointTip(run,checks) {
  return [`s${run.seed} · ${trackName(run.track)} · 赢家请求 ${checks[0].ordinal} · ${checks[0].solver}`,
    ...checks.map(c => `封存 B=${c.budget} · 开发集目标 ${fixed(c.objective,6)} · Hook ${Object.values(c.hooks).join(' + ')} 行\n请求 ${fmt(c.usage.attempted_requests,0)} · 墙钟 ${fmt(c.wall)} 秒 · 已计价 $${fixed(c.usage.priced_cost_usd,6)}\n输入 ${fmt(c.usage.input_tokens,0)} · 输出 ${fmt(c.usage.output_tokens,0)} · 缓存 ${fmt(c.usage.cached_tokens,0)} tokens`)].join('\n');
}
function roundShade(view,x,top,bottom,seed=null) {
  if (!selectedRound || (seed != null && selectedRound.seed !== seed) || selectedRound.end < selectedRound.start) return;
  const a = x(selectedRound.start-.5), b = x(Math.min(400,selectedRound.end+.5));
  svg(view,'rect',{x:a,y:top,width:b-a,height:bottom-top,fill:'#165dff',opacity:.1,'pointer-events':'none'});
}
function renderDev() {
  hideTip();
  const runs = activeRuns();
  legend('dev-legend',[...runs.map(r => [runColor(r.seed),`s${r.seed}`]),['#ffce55','封存赢家'],['#8596ad','虚线：封存请求数']]);
  const view = chart('dev-chart',1050,330,'有效候选、单调最优轨迹与封存赢家');
  const left=devLeft,right=devRight,top=43,bottom=286;
  const x=scale(0,400,left,right);
  const scores=runs.flatMap(r => r.candidates.filter(c => c.outcome === 'valid_candidate' || c.eligible).map(c => c.objective));
  const [lo,hi]=extent(scores,.13), y=scale(lo,hi,bottom,top);
  yGrid(view,y,ticks(lo,hi),left,right,v => fixed(v,2));
  roundShade(view,x,top,bottom);
  for (const b of new Set(runs.flatMap(r => r.checkpoints.map(c => c.budget)))) {
    line(view,x(b),top-10,x(b),bottom,{stroke:'#7e8fa7','stroke-dasharray':'5 4'});
    text(view,x(b),top-17,`封存 ${b}`,{'text-anchor':b===400?'end':'middle'});
  }
  for (const run of runs) {
    const c=runColor(run.seed);
    for (const row of run.candidates) {
      if (row.outcome !== 'valid_candidate' || row.objective == null) continue;
      const mark=svg(view,'circle',{cx:x(row.ordinal),cy:y(row.objective),r:2.5,fill:c,opacity:.48});
      hover(mark,`s${run.seed} · 请求 ${row.ordinal}\n开发集惩罚目标 ${fixed(row.objective,6)}\n完成率 ${fmt(row.completion == null ? null : row.completion*100)}%`,false);
    }
    const last=run.envelope.at(-1);
    if (last) curve(view,[...run.envelope,[400,last[1]]],x,y,{stroke:c},true);
  }
  runs.forEach((run,index) => {
    const winners = new Map();
    for (const c of run.checkpoints) {
      if (!winners.has(c.ordinal)) winners.set(c.ordinal,[]);
      winners.get(c.ordinal).push(c);
    }
    for (const [ordinal,checks] of winners) {
      const px=x(ordinal), py=y(checks[0].objective);
      const mark=star(view,px,py);
      mark.dataset.ordinal=String(ordinal);
      mark.dataset.cutoffs=checks.map(c => c.budget).join(',');
      hover(mark,checkpointTip(run,checks));
      text(view,px+(ordinal>=380?-12:12),py+(index%2===0?-9:15),`B${checks.map(c => c.budget).join('/')}`,{
        fill:'#734700','text-anchor':ordinal>=380?'end':'start','pointer-events':'none'
      });
    }
  });
  for (const v of [0,36,100,200,300,400]) text(view,x(v),bottom+20,v,{'text-anchor':'middle'});
  text(view,left,16,'开发集惩罚目标（越低越好）',{class:'chart-label'});
  text(view,right,bottom+38,'物理请求序号',{'text-anchor':'end'});
  renderLanes(runs);
  renderRounds(runs);
}

function renderLanes(runs) {
  legend('lane-legend',[
    ...['valid_candidate','invalid_candidate','eoh_skipped','provider_failed','connectivity_failed','http_error','strong','weak'].map(k => categories[k])
  ]);
  const rowH=17, groupH=66, left=devLeft, right=devRight;
  const view=chart('dev-lanes',1050,30+runs.length*groupH,'生成结果、请求状态与模型路由');
  const x=scale(0,400,left,right);
  runs.forEach((run,i) => {
    const top=13+i*groupH;
    text(view,left-10,top+10,`s${run.seed} · 生成`,{'text-anchor':'end',fill:runColor(run.seed)});
    text(view,left-10,top+rowH+10,'请求',{'text-anchor':'end'});
    text(view,left-10,top+2*rowH+10,'路由',{'text-anchor':'end'});
    for (const req of run.requests) {
      [req.outcome,req.state,req.route].forEach((key,lane) => {
        const fill=categories[key]?.[0] ?? '#eef2f8';
        const mark=svg(view,'rect',{x:x(req.ordinal)-1,y:top+lane*rowH,width:2.1,height:12,fill});
        hover(mark,`s${run.seed} · 请求 ${req.ordinal} · ${req.purpose ?? '—'}\n生成 ${label(req.outcome)} · 请求 ${label(req.state)} · HTTP ${fmt(req.http,0)}\n${req.error ?? '—'} · 路由 ${label(req.route)} · 逻辑请求 ${fmt(req.logical,0)} · 重试 ${fmt(req.retry,0)}\n请求模型 ${req.requested ?? '—'} · 服务模型 ${req.served ?? '—'}`,false);
      });
    }
    roundShade(view,x,top,top+46,run.seed);
    for (const cp of run.checkpoints) line(view,x(cp.budget),top-2,x(cp.budget),top+46,{stroke:'#63798e','stroke-dasharray':'3 3','pointer-events':'none'});
  });
  for (const v of [0,100,200,300,400]) text(view,x(v),runs.length*groupH+12,v,{'text-anchor':'middle'});
}
function renderRounds(runs) {
  const rows = runs.flatMap(run => run.rounds.map(round => {
    const active=selectedRound?.seed === run.seed && selectedRound.round === round.round;
    const id=`round-${run.seed}-${round.round}`;
    const button=html('button',`第 ${round.round} 轮`,{id,type:'button','aria-pressed':String(active)});
    button.addEventListener('click',() => {
      selectedRound=active ? null : {...round,seed:run.seed};
      renderDev();
      $(id)?.focus();
    });
    return [`s${run.seed}`,button,round.end>=round.start ? `${round.start}–${round.end}` : '—',fmt(round.objective,4),signed(round.delta,4),fmt(round.outer,0),fmt(round.inner,0),fmt(round.supported,0),fmt(round.refuted,0)];
  }));
  table('rounds',['种子','轮次','请求区间','开发集目标','较上轮','外层请求','内层请求','已支持假设','已反驳假设'],rows);
}

const comparatorColors=['#627892','#008c37','#be2e31','#7955a2'];
function renderScaling() {
  hideTip();
  const key=$('metric').value, size=$('size').value;
  const notes={penalized:'惩罚均值覆盖全部观察。未完成项按参考目标的两倍计入。确定性对照保留完成值，详情同时提供严格截止惩罚。',
    raw:'原始均值使用全部可行解，包含超时时保留的可行解。',
    exact:'Exact-k 达成率以全部观察为分母。详情同时显示自由车队可行率。',timeouts:'超时数基于记录的预算耗尽标记。'};
  $('metric-note').textContent=`${notes[key]} 彩色小点为单个种子，实线和方块为跨种子均值。`;
  const entries = groupSpecs.map(([keyId,name]) => {
    const rows=data.seeds.map(seed => subset(data.blind[specCell(keyId,seed)],size));
    const values=rows.map(row => metricValue(row,key));
    return {keyId,name,values,mean:avg(values.filter(Number.isFinite)),n:rows.map(r=>r.n)};
  });
  const refs=data.comparators.map(id => [id,metricValue(subset(data.blind[id],size),key)]);
  const [lo,hi]=extent([...entries.flatMap(e=>e.values),...refs.map(r=>r[1])],.12);
  const left=74,right=780,top=28,bottom=266;
  const x=scale(0,entries.length-1,left+35,right-27), y=scale(lo,hi,bottom,top);
  const view=chart('scaling-chart',1050,305,`${sizeName(size)} · ${metricLabels[key]}`);
  const vfmt=v=>v==null ? '—' : key==='exact' ? `${fmt(v,1)}%` : fmt(v,key==='timeouts'?1:2);
  yGrid(view,y,ticks(lo,hi),left,right,vfmt);
  text(view,left,14,metricLabels[key]+' · '+sizeName(size),{class:'chart-label'});
  refs.forEach(([name,value],i) => {
    const color=comparatorColors[i], yy=top+16+24*i;
    if (value != null) line(view,left,y(value),right,y(value),{stroke:color,'stroke-dasharray':`${3+i} 4`,opacity:.7});
    line(view,792,yy,811,yy,{stroke:color,'stroke-dasharray':`${3+i} 4`});
    text(view,819,yy+4,`${name} · ${vfmt(value)}`,{fill:color});
  });
  curve(view,entries.slice(0,4).map((e,i)=>[i,e.mean]),x,y,{stroke:'#165dff'});
  entries.forEach((entry,i) => {
    const px=x(i);
    text(view,px,bottom+23,entry.name,{'text-anchor':'middle'});
    entry.values.forEach((value,j) => {
      if (value == null) return;
      hover(svg(view,'circle',{cx:px+(j-1)*12,cy:y(value),r:4,fill:seeds[j],stroke:'#fff'}),
        `${entry.name} · s${data.seeds[j]}\n${metricLabels[key]} ${vfmt(value)} · n=${entry.n[j]}`);
    });
    if (entry.mean != null) {
      const c=i<4?'#165dff':trackColors[entry.keyId];
      hover(svg(view,'rect',{x:px-4.5,y:y(entry.mean)-5,width:9,height:9,fill:'#fff',stroke:c,'stroke-width':2}),
        `${entry.name} · 种子均值 ${vfmt(entry.mean)}\n${entry.values.filter(Number.isFinite).length}/${data.seeds.length} 个种子`);
    }
  });
  renderSlices(key,size);
}

function latencyTip(name,size,group,metrics) {
  const q=metrics.solve;
  return [`${name} · ${sizeName(size)} · ${group.deadline} ms${group.enforced?'':'（完整轨迹）'}`,
    `计时 ${metrics.timed}/${metrics.n} · 时限内完成 ${metrics.within}/${metrics.n} · 超时 ${metrics.timeouts}`,
    `p10 ${fmt(q.p10)} · p25 ${fmt(q.p25)} · p50 ${fmt(q.p50)} · p75 ${fmt(q.p75)} ms`,
    `p90 ${fmt(q.p90)} · p95 ${fmt(q.p95)} · 最大 ${fmt(q.max)} ms`,
    `≤500 ms ${metrics.under500}/${metrics.timed} · ≤2000 ms ${metrics.under2000}/${metrics.timed}`].join('\n');
}
function renderSlices(key,size) {
  const seed=Number($('slice-seed').value), candidate=$('slice-candidate').value, reference=$('slice-reference').value;
  const primary=specCell(candidate,seed), control=cell('timeout_2000ms',seed);
  const picked=[...new Set([primary,control,reference,'l3_ctrl@2000ms','cw_relocate_2opt@500ms'])];
  const shortName=id=>id===primary ? groupName(candidate) : id===control ? groupName('timeout_2000ms') : id;
  const focusSizes=size==='overall' ? sizes : [size];
  const rows=focusSizes.flatMap(sz=>picked.map(id=>({id,sz,m:subset(data.blind[id],sz)})));
  const h=46+rows.length*24, left=216, right=1020;
  const view=chart('latency',1050,h,'时延分位数与 500、2000 毫秒红线');
  const xmax=Math.max(2110,...rows.map(row=>row.m.solve.max ?? 0));
  const x=scale(0,xmax,left,right);
  for (const [deadline,color] of [[500,'#be2e31'],[2000,'#c15100']]) {
    line(view,x(deadline),20,x(deadline),h-11,{stroke:color,'stroke-dasharray':'5 3'});
    text(view,x(deadline)-3,15,`${deadline} ms`,{'text-anchor':'end',fill:color});
  }
  rows.forEach(({id,sz,m},i)=>{
    const yy=33+i*24, q=m.solve;
    const color=id===primary?'#165dff':id===control?'#008c37':'#617489';
    if (i%picked.length===0) line(view,0,yy-11,right,yy-11,{class:'grid'});
    text(view,0,yy+4,`${sizeName(sz)} · ${shortName(id)}`);
    if (q.p50 == null) return;
    const marks=svg(view,'g');
    svg(marks,'rect',{x:left,y:yy-9,width:right-left,height:18,fill:'transparent'});
    line(marks,x(q.p10),yy,x(q.p95),yy,{stroke:color,'stroke-width':1.5});
    line(marks,x(q.p25),yy,x(q.p75),yy,{stroke:color,'stroke-width':6,'stroke-linecap':'round'});
    line(marks,x(q.p90),yy-3,x(q.p90),yy+3,{stroke:color});
    line(marks,x(q.max),yy-5,x(q.max),yy+5,{stroke:color,'stroke-width':1.5});
    svg(marks,'circle',{cx:x(q.p50),cy:yy,r:4,fill:'#fff',stroke:color,'stroke-width':1.6});
    hover(marks,latencyTip(shortName(id),sz,data.blind[id],m));
  });
  renderHeat(key,focusSizes,data.blind[primary],data.blind[reference]);
  table('blind-detail', ['方案','样本','完成','时限内完成','自由车队可行','Exact-k','超时','原始均值','完成项均值','惩罚均值','严格截止惩罚'],
    [...groupSpecs.map(([id])=>[groupName(id),specCell(id,seed)]), ...data.comparators.map(id=>[id,id])].map(([name,id])=>{
      const m=subset(data.blind[id],size);
      return [name,m.n,m.completed,m.within,`${m.feasible}/${m.n} (${fmt(pct(m.feasible,m.n))}%)`,`${m.exact}/${m.n} (${fmt(pct(m.exact,m.n))}%)`,m.timeouts,
        fmt(m.raw,4),fmt(m.completedMean,4),fmt(m.penalized,4),fmt(m.strict,4)];
    }));
}
function renderHeat(key,focusSizes,primary,reference) {
  const columns=[['loose','centre'],['loose','eccentric'],['tight','centre'],['tight','eccentric']];
  const regimeId=r=>`${r.size}/${r.spatial}/${r.capacity}/${r.depot}`;
  const other=new Map(reference.regimes.map(r=>[regimeId(r),r]));
  const deltas=new Map(primary.regimes.filter(r=>focusSizes.includes(r.size)).map(r=>{
    const id=regimeId(r), opposite=other.get(id);
    const a=metricValue(r,key), b=opposite ? metricValue(opposite,key) : null;
    return [id,{value:a==null||b==null?null:a-b,n:Math.min(r.n,opposite?.n ?? 0),a,b}];
  }));
  const max=Math.max(0,...Array.from(deltas.values(),d=>Math.abs(d.value ?? 0)));
  const rows=focusSizes.flatMap(sz=>['uniform','clustered','mixed'].map(sp=>[
    `${sizeName(sz)} · ${labelMap[sp]}`,
    ...columns.map(([cap,dep])=>{
      const d=deltas.get(`${sz}/${sp}/${cap}/${dep}`);
      if (d?.value == null) return '—';
      const cell=html('div',`${signed(d.value,key==='timeouts'?0:2)}${key==='exact'?' pp':''}`,{title:`方案 ${fmt(d.a,4)} · 参考 ${fmt(d.b,4)}`});
      cell.append(html('small',`(${d.n})`));
      const better=key==='exact'?d.value>0:d.value<0;
      const opacity=max ? .08 + .26*Math.abs(d.value)/max : 0;
      if (d.value!==0) cell.style.backgroundColor=better?`rgba(0,140,55,${opacity})`:`rgba(190,46,49,${opacity})`;
      return cell;
    })
  ]));
  table('heat',['规模与空间结构',...columns.map(([cap,dep])=>`${labelMap[cap]} · ${labelMap[dep]}`)],rows).classList.add('heat');
}

function renderForest() {
  hideTip();
  const family=$('pair-family').value;
  const rows=data.stats.filter(row=>family==='all'||row.family===family);
  const left=320,right=792,h=rows.length*27+73;
  const [lo,hi]=extent([0,...rows.flatMap(r=>r.ci)],.05);
  const x=scale(lo,hi,left,right);
  const view=chart('forest',1050,h,'种子级 Bootstrap 相对收益森林图');
  text(view,0,20,'候选 / 参考 · 种子',{class:'chart-label'});
  text(view,left,20,'相对收益与 Bootstrap 95% 区间',{class:'chart-label'});
  text(view,818,20,'胜 / 平 / 负',{class:'chart-label'});
  text(view,975,20,'p_Holm',{class:'chart-label'});
  line(view,x(0),25,x(0),h-28,{stroke:'#73879e','stroke-dasharray':'4 3'});
  rows.forEach((r,i)=>{
    const yy=39+i*27;
    if (i%2===0) svg(view,'rect',{x:0,y:yy-11,width:1048,height:24,fill:'#f2f6fb',opacity:.7});
    const name=`${groupName(r.candidate)} / ${groupName(r.reference)} · s${r.seed}`;
    const lines=`${name}\n相对收益 ${signed(r.gain,4)}% · 95% 区间 [${r.ci.map(v=>signed(v,4)).join(', ')}]%\n胜/平/负 ${r.wtl.join('/')} · n=${r.n}\np_Holm ${pValue(r.pHolm)} · 共同完成 ${r.commonN} · 收益 ${signed(r.commonGain,4)}%`;
    text(view,0,yy+4,name);
    const color=r.pHolm<.05&&r.pHolm!=null?(r.gain>0?'#008c37':'#be2e31'):'#657b95';
    const mark=svg(view,'g');
    if (r.ci.every(Number.isFinite)) {
      line(mark,x(r.ci[0]),yy,x(r.ci[1]),yy,{stroke:color,'stroke-width':2});
      for (const q of r.ci) line(mark,x(q),yy-3,x(q),yy+3,{stroke:color});
    }
    if (r.gain != null) svg(mark,'circle',{cx:x(r.gain),cy:yy,r:4,fill:color});
    let start=818;
    r.wtl.forEach((count,j)=>{
      const width=r.n?95*count/r.n:0;
      if (width) svg(mark,'rect',{x:start,y:yy-4,width,height:8,fill:['#008c37','#aab9ca','#d95c60'][j]});
      start+=width;
    });
    hover(mark,lines);
    text(view,920,yy+4,r.wtl.join('/'));
    text(view,975,yy+4,pValue(r.pHolm));
  });
  for (const v of ticks(lo,hi,4)) text(view,x(v),h-13,`${fmt(v,2)}%`,{'text-anchor':'middle'});
  table('pair-table',['候选','参考','种子','全量配对','惩罚收益','95% 区间','胜/平/负','Wilcoxon p','p_Holm','共同完成','共同完成原始收益'],
    rows.map(r=>[groupName(r.candidate),groupName(r.reference),r.seed,r.n,`${signed(r.gain,4)}%`,r.ci.map(v=>`${signed(v,4)}%`).join(' 至 '),
      r.wtl.join('/'),r.p==null?'—':r.p.toExponential(2),pValue(r.pHolm),r.commonN,r.commonGain==null?'—':`${signed(r.commonGain,4)}%`]));
}

function renderOperators() {
  hideTip();
  const track=$('operator-track').value;
  const rows=data.operators.filter(row=>track==='all'||row.track===track);
  legend('operator-legend',Object.entries(trackColors).filter(([key])=>track==='all'||key===track).map(([t,c])=>[c,trackName(t)]));
  const left=55,right=510,top=24,bottom=226;
  const view=chart('anytime',530,267,'select_16 跨时间检查点的平均路径成本');
  const xs=[10,25,100,250,500], x=scale(0,4,left,right);
  const [lo,hi]=extent(rows.flatMap(r=>r.anytime.map(p=>p[1])),.14), y=scale(lo,hi,bottom,top);
  yGrid(view,y,ticks(lo,hi),left,right,v=>fixed(v,3));
  for (const ms of xs) text(view,x(xs.indexOf(ms)),bottom+19,ms,{'text-anchor':'middle'});
  text(view,left,15,'平均路径长度',{class:'chart-label'});
  text(view,right,261,'检查点（ms）',{'text-anchor':'end'});
  rows.forEach(row=>{
    const color=trackColors[row.track], dash=['','5 3','2 3'][data.seeds.indexOf(row.seed)];
    const px=ms=>x(xs.indexOf(ms));
    curve(view,row.anytime,px,y,{stroke:color,'stroke-dasharray':dash,opacity:.82});
    for (const [ms,v] of row.anytime) {
      if (v==null) continue;
      hover(svg(view,'circle',{cx:px(ms),cy:y(v),r:3,fill:color,stroke:'#fff'}),
        `${trackName(row.track)} · s${row.seed} · ${row.solver}\n${ms} ms · 均值 ${fixed(v,4)} · 有效 ${row.valid}/16`);
    }
  });
  const scatter=chart('operator-scatter',530,267,'Hook 总行数与 n=200 求解时延中位数');
  const entries=rows.map(row=>({row,loc:Object.values(row.hooks).reduce((n,value)=>n+value,0),median:data.blind[row.group].sizes.n200.solve.p50}));
  const [minLoc,maxLoc]=extent(entries.map(r=>r.loc),.18), sx=scale(minLoc,maxLoc,left,right);
  const [minMs,maxMs]=extent(entries.map(r=>r.median),.15), sy=scale(minMs,maxMs,bottom,top);
  yGrid(scatter,sy,ticks(minMs,maxMs),left,right,v=>fmt(v,0));
  for (const loc of ticks(minLoc,maxLoc)) text(scatter,sx(loc),bottom+20,fmt(loc,0),{'text-anchor':'middle'});
  text(scatter,left,15,'时延 p50（ms）',{class:'chart-label'});
  text(scatter,right,261,'Hook 总行数',{'text-anchor':'end'});
  for (const {row,loc,median} of entries) {
    if (median==null) continue;
    const mark=svg(scatter,'circle',{cx:sx(loc),cy:sy(median),r:6,fill:trackColors[row.track],stroke:'#fff','stroke-width':1.2});
    hover(mark,`${trackName(row.track)} · s${row.seed} · ${row.solver}\n${Object.entries(row.hooks).map(([h,n])=>`${h} ${n} 行`).join(' + ')}\nn=200 · p50 ${fmt(median)} ms · 时限 ${data.blind[row.group].deadline} ms`);
  }
}

function operatorCards() {
  const cards=[
    ['三阶段 Gumbel 退火','ckpt_cand_8c4dfb41aa','按搜索进度与停滞程度在强化、过渡、分散三个阶段切换。以线路余量和停靠稀疏度引导移除，再结合节省最大客户附近的径向距离与确定性 Gumbel 噪声。'],
    ['Gibbs–Boltzmann 配额阶梯','ckpt_cand_22af9ec1ab','把移除节省占线路长度的比例、归一化载重和相对场站距离组合为无量纲能量。用随搜索进度和停滞变化的逆温度控制 Gibbs 权重，再用累计概率形成排序阶梯。'],
  ];
  for (const [title,id,description] of cards) {
    const row=data.operators.find(r=>r.solver===id);
    if (!row) continue;
    const card=html('article',null,{class:'operator'});
    card.append(html('h3',title),html('span',`${id} · s${row.seed}`,{class:'solver'}),html('p',description));
    $('operator-cards').append(card);
  }
}

overview();
options('dev-track',trackOptions);
options('dev-seed',seedOptions);
options('size',[['overall','全部规模'],...sizes.map(sz=>[sz,sizeName(sz)])]);
options('metric',Object.entries(metricLabels));
options('slice-seed',seedOptions);
options('slice-candidate',groupSpecs,'curve_400');
options('slice-reference',data.comparators.map(key=>[key,key]),'l3_ctrl@500ms');
options('pair-family',[['baseline','2000 ms 与确定性对照'],['published','已发布的预算与控制比较'],['all','全部比较']]);
options('operator-track',[['all','全部轨道'],...trackOptions]);
for (const id of ['dev-track','dev-seed']) $(id).addEventListener('change',()=>{selectedRound=null;renderDev();});
$('compare-seeds').addEventListener('click',()=>{
  compareSeeds=!compareSeeds;
  selectedRound=null;
  $('dev-seed').disabled=compareSeeds;
  $('compare-seeds').setAttribute('aria-pressed',String(compareSeeds));
  renderDev();
});
for (const id of ['size','metric','slice-seed','slice-candidate','slice-reference']) $(id).addEventListener('change',renderScaling);
$('pair-family').addEventListener('change',renderForest);
$('operator-track').addEventListener('change',renderOperators);
window.addEventListener('resize',hideTip);
window.addEventListener('scroll',hideTip,true);
renderDev();
renderScaling();
renderForest();
renderOperators();
operatorCards();
"""


def render_html(payload: Mapping[str, Any]) -> str:
    document = PAGE.replace("__REPORT_APP__", APP, 1).replace("__REPORT_DATA__", _safe_js_json(payload), 1)
    if FORBIDDEN.search(document):
        raise ValueError("Restricted field or blind evaluation key found in report")
    return document


def write_report(root: Path = REPO) -> Path:
    root = root.resolve()
    destination = root / OUTPUT
    if destination.parent.resolve(strict=True) != destination.parent or destination.is_symlink():
        raise ValueError("Invalid report destination")
    document = render_html(build_payload(root))
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(document)
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(write_report().relative_to(REPO).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
