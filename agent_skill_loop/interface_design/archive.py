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
