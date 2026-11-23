"""Stepping-stone Archive feedback and AST/behavior novelty guard tool."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID
from agent_skill_loop.interface_design.archive import (
    ComplementaryArchive,
    compute_quality_time_pareto,
    compute_weakest_regimes_feedback,
)
from agent_skill_loop.interface_design.blind_commitment import assert_suite_allowed_for_interactive_role
from research_agent.contracts import sha256_text


class SteppingStoneArchiveTool:
    """Wrap ComplementaryArchive with dev-only regime feedback & duplicate novelty guard."""

    def __init__(
        self,
        run_dir: Path,
        *,
        dev_suite_id: str = "cvrp_dev_hetero_24",
        dev_split: str = "dev_train",
    ) -> None:
        self.run_dir = Path(run_dir).resolve()
        self.dev_suite_id = str(dev_suite_id)
        self.dev_split = str(dev_split)
        assert_suite_allowed_for_interactive_role(self.dev_suite_id, role="feedback_archive")
        self.archive = ComplementaryArchive(self.run_dir / "archive")
        self.records_path = self.run_dir / "archive" / "dev_instance_records.jsonl"
        self.novelty_path = self.run_dir / "archive" / "novelty_signatures.json"
        self._records: list[dict[str, Any]] = []
        self._signatures: dict[str, dict[str, Any]] = {}
        if self.records_path.is_file():
            self._records = [
                json.loads(line)
                for line in self.records_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        if self.novelty_path.is_file():
            self._signatures = json.loads(self.novelty_path.read_text(encoding="utf-8"))

        suite = load_profile_suite(BENCHMARK_ID, self.dev_suite_id, split=self.dev_split)
        assert_suite_allowed_for_interactive_role(self.dev_suite_id, suite, role="feedback_archive")
        self._inst_meta = {str(inst["instance_id"]): inst for inst in suite["instances"]}

    @staticmethod
    def canonical_ast_sha256(code: str) -> str:
        try:
            tree = ast.parse(code)
            return sha256_text(ast.unparse(tree))
        except SyntaxError:
            return sha256_text(code.strip())

    def check_and_record_novelty(self, *, code: str, status: str = "seen") -> dict[str, Any]:
        sig = self.canonical_ast_sha256(code)
        prior = self._signatures.get(sig)
        is_dup = prior is not None
        self._signatures[sig] = {"status": status}
        self.novelty_path.parent.mkdir(parents=True, exist_ok=True)
        self.novelty_path.write_text(json.dumps(self._signatures, indent=2) + "\n", encoding="utf-8")
        return {"ast_sha256": sig, "duplicate": is_dup, "prior": prior}

    def register_solver_with_dev_records(
        self,
        *,
        frozen_solver: Mapping[str, Any],
        arm_id: str,
        search_seed: int,
        budget_id: str,
        dev_records: Sequence[Mapping[str, Any]],
        mean_objective: float | None,
        solve_ms_mean: float | None,
        resource_ledger: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        sid = str(frozen_solver["solver_id"])
        entry = self.archive.register(
            frozen_solver,
            arm_id=arm_id,
            search_seed=search_seed,
            budget_id=budget_id,
            suite_metrics={
                "suite_id": self.dev_suite_id,
                "mean_tour_length": mean_objective,
                "solve_ms_mean": solve_ms_mean,
            },
            resource_ledger=resource_ledger,
        )
        with self.records_path.open("a", encoding="utf-8", newline="\n") as handle:
            for r in dev_records:
                rec = {**dict(r), "suite_id": self.dev_suite_id, "algorithm_id": sid}
                self._records.append(rec)
                handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.check_and_record_novelty(code=str(frozen_solver["hook_code"]), status="accepted")
        return entry

    def summary(self) -> dict[str, Any]:
        manifest_path = self.archive.archive_dir / "archive_manifest.json"
        entries = json.loads(manifest_path.read_text(encoding="utf-8")).get("solvers", []) if manifest_path.is_file() else []
        solver_ids = [str(e["solver_id"]) for e in entries]
        pareto = compute_quality_time_pareto(entries)
        if solver_ids and self._records:
            fb = compute_weakest_regimes_feedback(
                self._records,
                suite_id=self.dev_suite_id,
                solver_ids=solver_ids,
                instance_metadata=self._inst_meta,
            )
        else:
            fb = {"suite_id": self.dev_suite_id, "portfolio": None, "weakest_regimes": []}
        return {
            "solver_count": len(entries),
            "pareto_frontier": pareto,
            "portfolio": fb["portfolio"],
            "weakest_regimes": fb["weakest_regimes"],
            "known_signatures_count": len(self._signatures),
        }
