"""Session Runtime driver tool for Research Agent (reuses official Session state machine)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID
from agent_skill_loop.interface_design.blind_commitment import assert_suite_allowed_for_interactive_role
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver
from agent_skill_loop.interface_design.runtime import evaluate_frozen_interface_solver
from agent_skill_loop.request_budget import PersistentRequestBudget
from agent_skill_loop.session_actions import (
    collect,
    execute,
    finish_round,
    read_evaluation,
    submit_evaluation,
    submit_plan,
)
from agent_skill_loop.session_runtime import initialize_session, read_state
from research_agent.contracts import AgentConfig, atomic_write_json


class SessionRunnerTool:
    """Execute or crash-resume one round via official Session Runtime sharing PersistentRequestBudget."""

    def __init__(self, *, run_dir: Path, config: AgentConfig, budget: PersistentRequestBudget) -> None:
        self.run_dir = Path(run_dir).resolve()
        self.config = config
        self.budget = budget
        self.session_dir = self.run_dir / "session_run"
        self.plans_dir = self.run_dir / "agent_artifacts" / "session_plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)

    def ensure_initialized(self) -> dict[str, Any]:
        if (self.session_dir / "session.sqlite3").is_file():
            return read_state(run=self.session_dir)
        eoh_endpoint = "mock://local" if self.config.mode == "mock" else self.config.endpoint
        return initialize_session(
            output=self.session_dir,
            operation_id=f"init_{self.config.run_id}",
            eoh_model=self.config.eoh_model,
            eoh_endpoint=eoh_endpoint,
            eoh_api_key_env=self.config.api_key_env,
            eoh_max_requests=self.config.total_request_cap,
            eoh_round_max_requests=None,
            engine_wall_seconds=self.config.wall_seconds,
            solver_timeout=self.config.candidate_timeout_s,
            request_timeout=self.config.request_timeout_s,
            memory_enabled=False,
            agent_guidance=bool(self.config.inject_static_kb_clues),
            seed=self.config.search_seed,
            count=self.config.dev_instance_count,
            size=self.config.dev_instance_size,
            search_policy_defaults={
                "pop_size": self.config.eoh_pop_size,
                "n_pop": self.config.eoh_n_pop,
                "max_sample_nums": self.config.eoh_max_sample_nums,
            },
            persistent_budget={
                "ledger_path": str(self.budget.ledger_path),
                "max_requests": self.budget.max_requests,
                "run_id": self.budget.run_id,
            },
        )

    def run_round(
        self,
        *,
        round_id: int,
        template_id: str,
        postprocess_mode: str,
        direction: str,
        hypothesis: str,
        cited_kb_ids: Sequence[str] = (),
        diagnostic_ref: Mapping[str, Any] | None = None,
        rationale: str = "",
        is_final_round: bool = False,
        eval_dev_suite: bool = True,
    ) -> dict[str, Any]:
        if self.config.allowed_templates and template_id not in self.config.allowed_templates:
            raise ValueError(f"template_not_allowed:{template_id}")
        if self.config.allowed_postprocess_modes and postprocess_mode not in self.config.allowed_postprocess_modes:
            raise ValueError(f"postprocess_not_allowed:{postprocess_mode}")

        self.ensure_initialized()
        prev_used = self.budget.used
        st = read_state(run=self.session_dir)

        # Resume-safe progression across SQLite round states
        cur_round = int(st.get("round_id") or 1)
        round_state = str(st.get("state") or "")
        ver = int(st["state_version"])

        if st.get("run_state") in {"COMPLETED", "STOPPED", "FAILED"}:
            return {
                "round_id": cur_round,
                "session_status": st.get("run_state"),
                "round_state": round_state,
                "frozen_solver": None,
                "dev_eval": None,
                "crossed_checkpoints": [],
            }

        if round_state == "WAITING_FOR_PLAN":
            plan_path = self.plans_dir / f"plan_r{cur_round:04d}.json"
            plan_doc = {
                "round_id": cur_round,
                "direction": direction,
                "operations": [
                    {
                        "type": "replace",
                        "target": template_id,
                        "mechanism": rationale or f"Evolve hook under {template_id} ({postprocess_mode}).",
                    }
                ],
                "preserve": "Route feasibility, strict time budget, and scale invariance.",
                "feedback_basis": st.get("feedback_basis"),
                "memory_basis": [],
                "reference_skill_ref": st["incumbent"]["ref"] if st.get("incumbent") else None,
                "hypothesis": hypothesis,
                "interface_selection": {
                    "template_id": template_id,
                    "template_version": "v1",
                    "postprocess_mode": postprocess_mode,
                    "time_budget_ms": float(self.config.instance_time_budget_ms),
                    "template_options": {"inject_static_kb_clues": bool(self.config.inject_static_kb_clues)},
                    "cited_kb_ids": list(cited_kb_ids),
                    "diagnostic_ref": dict(diagnostic_ref) if diagnostic_ref else None,
                    "rationale": rationale or f"Round {cur_round} interface selection.",
                },
            }
            plan_path.write_text(json.dumps(plan_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            sub = submit_plan(
                run=self.session_dir,
                operation_id=f"plan_r{cur_round}_{self.config.run_id}",
                expected_state_version=ver,
                file=plan_path,
            )
            ver = int(sub["state_version"])
            st = read_state(run=self.session_dir)
            round_state = str(st.get("state") or "")

        if round_state == "READY_TO_EXECUTE" and "execute" in (st.get("allowed_actions") or ()):
            exe = execute(
                run=self.session_dir,
                operation_id=f"exec_r{cur_round}_{self.config.run_id}",
                expected_state_version=ver,
            )
            ver = int(exe["state_version"])
            st = read_state(run=self.session_dir)
            round_state = str(st.get("state") or "")

        if round_state == "READY_TO_EXECUTE" and "collect" in (st.get("allowed_actions") or ()):
            deadline = time.monotonic() + float(self.config.wall_seconds)
            while True:
                t_info = (st.get("result") or {}).get("task") or {}
                t_state = str(t_info.get("state") or "")
                if t_state in {"EXITED", "COLLECTED"} or t_state not in {"CREATED", "STARTING", "RUNNING", "STOP_REQUESTED"} or time.monotonic() >= deadline:
                    col = collect(
                        run=self.session_dir,
                        operation_id=f"collect_r{cur_round}_{self.config.run_id}",
                        expected_state_version=int(st["state_version"]),
                    )
                    if col.get("result", {}).get("collected") or time.monotonic() >= deadline or t_state not in {"CREATED", "STARTING", "RUNNING", "STOP_REQUESTED"}:
                        ver = int(col["state_version"])
                        st = read_state(run=self.session_dir)
                        round_state = str(st.get("state") or "")
                        break
                time.sleep(0.25)
                st = read_state(run=self.session_dir)

        ev_facts: dict[str, Any] = {}
        frozen_solver: dict[str, Any] | None = None
        if round_state in {"WAITING_FOR_EVALUATION", "READY_TO_FINISH", "ROUND_COMPLETED"}:
            ev_facts = read_evaluation(run=self.session_dir)["result"]
            f_ref = ev_facts.get("frozen_solver_ref")
            if f_ref and (self.session_dir / f_ref).is_file():
                frozen_solver = json.loads((self.session_dir / f_ref).read_text(encoding="utf-8"))

        if round_state == "WAITING_FOR_EVALUATION":
            eval_path = self.plans_dir / f"eval_r{cur_round:04d}.json"
            refs = ev_facts.get("evidence_refs") or [f"rounds/round_{cur_round:04d}/evaluation_facts.json"]
            eval_doc = {
                "plan_alignment": "aligned",
                "observations": [
                    {
                        "claim": f"Session round {cur_round} evaluated under {template_id}/{postprocess_mode}.",
                        "evidence_refs": list(refs[:1]),
                    }
                ],
                "hypotheses": [
                    {
                        "claim": hypothesis,
                        "confidence": "medium",
                        "evidence_refs": list(refs[:1]),
                    }
                ],
                "next_search_advice": {"direction": direction},
                "memory_action": {"kind": "disabled"},
            }
            eval_path.write_text(json.dumps(eval_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            se = submit_evaluation(
                run=self.session_dir,
                operation_id=f"se_r{cur_round}_{self.config.run_id}",
                expected_state_version=int(st["state_version"]),
                file=eval_path,
            )
            ver = int(se["state_version"])
            st = read_state(run=self.session_dir)
            round_state = str(st.get("state") or "")

        if round_state == "READY_TO_FINISH":
            decision = "complete" if (is_final_round or (self.budget.remaining is not None and self.budget.remaining <= 0)) else "continue"
            fin = finish_round(
                run=self.session_dir,
                operation_id=f"fin_r{cur_round}_{self.config.run_id}",
                expected_state_version=int(st["state_version"]),
                decision=decision,
            )
            st = fin

        curr_used = self.budget.used
        crossed = self.budget.check_checkpoints(prev_used, curr_used)

        dev_eval: dict[str, Any] | None = None
        if eval_dev_suite and frozen_solver is not None:
            assert_suite_allowed_for_interactive_role(self.config.dev_suite_id, role="diagnostic_interactive")
            suite = load_profile_suite(BENCHMARK_ID, self.config.dev_suite_id, split=self.config.dev_split)
            assert_suite_allowed_for_interactive_role(self.config.dev_suite_id, suite, role="diagnostic_interactive")
            fs = FrozenInterfaceSolver.from_dict(frozen_solver)
            dev_records = [
                evaluate_frozen_interface_solver(
                    fs,
                    inst,
                    distance_convention=suite["distance_convention"],
                    vehicle_limit_policy=suite["vehicle_limit_policy"],
                    time_budget_ms=self.config.instance_time_budget_ms,
                )
                for inst in suite["instances"]
            ]
            valid_lens = [float(r["tour_length"]) for r in dev_records if r.get("valid") and r.get("tour_length") is not None]
            solve_times = [float(r["solve_ms"]) for r in dev_records if r.get("solve_ms") is not None]
            dev_eval = {
                "suite_id": self.config.dev_suite_id,
                "valid_count": len(valid_lens),
                "instance_count": len(dev_records),
                "mean_tour_length": round(sum(valid_lens) / len(valid_lens), 6) if valid_lens else None,
                "solve_ms_mean": round(sum(solve_times) / len(solve_times), 4) if solve_times else None,
                "records": dev_records,
            }

        return {
            "round_id": cur_round,
            "session_status": st.get("run_state") or "ok",
            "round_state": st.get("state"),
            "evaluation_facts": ev_facts,
            "frozen_solver": frozen_solver,
            "dev_eval": dev_eval,
            "crossed_checkpoints": crossed,
            "requests_before": prev_used,
            "requests_after": curr_used,
        }
