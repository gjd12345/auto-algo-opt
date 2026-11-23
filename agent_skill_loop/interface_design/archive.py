"""Cross-paradigm solver archive for Milestone 2 (Phase 2B/2C).

Records frozen solver manifests, per-instance results, provenance, and computes
empirical quality / speed / complementarity statistics without premature hard-coded
retention pruning.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .contracts import FrozenInterfaceSolver


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ComplementaryArchive:
    """Durable archive of frozen Milestone 2 solvers and their per-instance workbench records."""

    def __init__(self, archive_dir: Path) -> None:
        self.archive_dir = Path(archive_dir).resolve()
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self.archive_dir / "archive_manifest.json"
        self._entries: dict[str, dict[str, Any]] = {}
        if self._manifest_path.is_file():
            doc = json.loads(self._manifest_path.read_text(encoding="utf-8"))
            for row in doc.get("solvers", []):
                self._entries[str(row["solver_id"])] = row

    def register(
        self,
        frozen_solver: FrozenInterfaceSolver | Mapping[str, Any],
        *,
        arm_id: str,
        search_seed: int | None = None,
        budget_id: str = "standard_500ms",
        suite_metrics: Mapping[str, Any] | None = None,
        resource_ledger: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        fs = frozen_solver if isinstance(frozen_solver, FrozenInterfaceSolver) else FrozenInterfaceSolver.from_dict(frozen_solver)
        entry = {
            "solver_id": fs.solver_id,
            "registered_at": _utc_now(),
            "arm_id": arm_id,
            "search_seed": search_seed,
            "budget_id": budget_id,
            "frozen_solver": fs.to_dict(),
            "suite_metrics": dict(suite_metrics or {}),
            "resource_ledger": dict(resource_ledger or {}),
        }
        self._entries[fs.solver_id] = entry
        self.save()
        return entry

    def list_solvers(self) -> list[FrozenInterfaceSolver]:
        return [FrozenInterfaceSolver.from_dict(e["frozen_solver"]) for e in self._entries.values()]

    def save(self) -> Path:
        payload = {
            "schema_version": "m2-complementary-archive/v1",
            "updated_at": _utc_now(),
            "solver_count": len(self._entries),
            "solvers": list(self._entries.values()),
        }
        self._manifest_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return self._manifest_path


def compute_portfolio_complementarity(
    per_instance_records: Sequence[Mapping[str, Any]],
    *,
    suite_id: str,
    solver_ids: Sequence[str],
) -> dict[str, Any]:
    """Compute SBS, VBS (oracle), win counts, and both SBS/VBS gap denominators on a suite."""
    by_inst: dict[str, dict[str, float]] = {}
    for rec in per_instance_records:
        if rec.get("suite_id") != suite_id:
            continue
        aid = str(rec.get("algorithm_id"))
        if aid not in solver_ids:
            continue
        if rec.get("status") == "ok" and rec.get("valid") and rec.get("tour_length") is not None:
            by_inst.setdefault(str(rec["instance_id"]), {})[aid] = float(rec["tour_length"])

    common_iids = sorted(iid for iid, mp in by_inst.items() if all(aid in mp for aid in solver_ids))
    if not common_iids:
        return {
            "suite_id": suite_id,
            "solver_ids": list(solver_ids),
            "common_completed_count": 0,
            "sbs_solver": None,
            "sbs_total": None,
            "vbs_total": None,
            "gap_over_sbs_pct": None,
            "gap_over_vbs_pct": None,
            "win_counts": {},
        }

    totals = {aid: float(sum(by_inst[iid][aid] for iid in common_iids)) for aid in solver_ids}
    sbs_solver = min(solver_ids, key=lambda a: totals[a])
    sbs_total = totals[sbs_solver]
    vbs_total = 0.0
    win_counts = {aid: 0 for aid in solver_ids}
    for iid in common_iids:
        best_a = min(solver_ids, key=lambda a: by_inst[iid][a])
        best_v = by_inst[iid][best_a]
        vbs_total += best_v
        win_counts[best_a] += 1

    return {
        "suite_id": suite_id,
        "solver_ids": list(solver_ids),
        "common_completed_count": len(common_iids),
        "mean_by_solver": {aid: round(totals[aid] / len(common_iids), 4) for aid in solver_ids},
        "sbs_solver": sbs_solver,
        "sbs_total": round(sbs_total, 4),
        "vbs_total": round(vbs_total, 4),
        "gap_over_sbs_pct": round(100.0 * (sbs_total - vbs_total) / max(sbs_total, 1e-12), 4),
        "gap_over_vbs_pct": round(100.0 * (sbs_total - vbs_total) / max(vbs_total, 1e-12), 4),
        "win_counts": win_counts,
    }


def compute_quality_time_pareto(entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return non-dominated stepping-stone solvers along (mean_objective, solve_ms_mean)."""
    pts: list[tuple[float, float, dict[str, Any]]] = []
    for e in entries:
        sm = e.get("suite_metrics") or {}
        obj = sm.get("mean_tour_length")
        if obj is None:
            obj = sm.get("mean_objective")
        ms = sm.get("solve_ms_mean", sm.get("mean_solve_ms", 0.0))
        if obj is None:
            continue
        pts.append((float(obj), float(ms or 0.0), dict(e)))
    pts.sort(key=lambda x: (x[0], x[1]))
    pareto: list[dict[str, Any]] = []
    best_ms = float("inf")
    for obj, ms, raw in pts:
        if ms < best_ms - 1e-9 or not pareto:
            best_ms = min(best_ms, ms)
            pareto.append({
                "solver_id": raw.get("solver_id"),
                "template_id": (raw.get("frozen_solver") or {}).get("template_id"),
                "mean_objective": round(obj, 6),
                "solve_ms_mean": round(ms, 4),
                "arm_id": raw.get("arm_id"),
            })
    return pareto


def compute_weakest_regimes_feedback(
    per_instance_records: Sequence[Mapping[str, Any]],
    *,
    suite_id: str,
    solver_ids: Sequence[str],
    instance_metadata: Mapping[str, Mapping[str, Any]] | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    """Summarize SBS/VBS complementarity and rank weakest dev regimes for next-round planning."""
    from .blind_commitment import assert_suite_allowed_for_interactive_role

    assert_suite_allowed_for_interactive_role(suite_id, role="feedback_archive")
    portfolio = compute_portfolio_complementarity(
        per_instance_records,
        suite_id=suite_id,
        solver_ids=solver_ids,
    )
    by_inst: dict[str, list[Mapping[str, Any]]] = {}
    for rec in per_instance_records:
        if rec.get("suite_id") == suite_id and str(rec.get("algorithm_id")) in solver_ids:
            by_inst.setdefault(str(rec["instance_id"]), []).append(rec)

    factor_buckets: dict[tuple[str, str], dict[str, Any]] = {}
    for iid, rows in by_inst.items():
        meta = dict((instance_metadata or {}).get(iid) or rows[0])
        valid_vals = [
            float(r["tour_length"])
            for r in rows
            if r.get("status") == "ok" and r.get("valid") and r.get("tour_length") is not None
        ]
        vbs_obj = min(valid_vals) if valid_vals else None
        exhausted = sum(1 for r in rows if r.get("outcome_class") == "budget_exhausted_feasible_incumbent")
        failed = sum(1 for r in rows if r.get("outcome_class") == "timeout_or_infeasible" or not r.get("valid"))
        refs = [float(r["reference_objective"]) for r in rows if r.get("reference_objective")]
        ref_val = refs[0] if refs else None
        rel_gap = ((vbs_obj - ref_val) / ref_val * 100.0) if (vbs_obj is not None and ref_val and ref_val > 0) else None
        for factor in ("size", "spatial", "depot_style", "capacity_level", "demand_dist"):
            fval = meta.get(factor)
            if fval is None:
                continue
            key = (factor, str(fval))
            b = factor_buckets.setdefault(key, {"gaps": [], "vbs": [], "exhausted": 0, "failed": 0, "count": 0})
            b["count"] += 1
            if vbs_obj is not None:
                b["vbs"].append(vbs_obj)
            if rel_gap is not None:
                b["gaps"].append(rel_gap)
            b["exhausted"] += int(exhausted > 0)
            b["failed"] += int(failed > 0)

    ranked: list[dict[str, Any]] = []
    for (factor, val), b in factor_buckets.items():
        mean_gap = sum(b["gaps"]) / len(b["gaps"]) if b["gaps"] else None
        mean_vbs = sum(b["vbs"]) / len(b["vbs"]) if b["vbs"] else None
        ranked.append({
            "factor": factor,
            "value": val,
            "instance_count": b["count"],
            "vbs_mean_objective": round(mean_vbs, 4) if mean_vbs is not None else None,
            "vbs_rel_gap_pct": round(mean_gap, 4) if mean_gap is not None else None,
            "exhausted_instances": b["exhausted"],
            "failed_instances": b["failed"],
        })
    ranked.sort(
        key=lambda item: (
            -item["failed_instances"],
            -item["exhausted_instances"],
            -(item["vbs_rel_gap_pct"] if item["vbs_rel_gap_pct"] is not None else -1e9),
            -(item["vbs_mean_objective"] or 0.0),
        )
    )
    return {
        "suite_id": suite_id,
        "portfolio": portfolio,
        "weakest_regimes": ranked[:top_k],
    }
