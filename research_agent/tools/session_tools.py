"""Session Runtime driver tool for Research Agent (reuses official Session state machine)."""

from __future__ import annotations

import json
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent_skill_loop.client import ProviderFailure
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID
from agent_skill_loop.interface_design.blind_eval_m32 import assert_milestone_suite_allowed_for_interactive_role
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver
from agent_skill_loop.interface_design.dynamic_eoh import derive_effective_batch_timeout_s
from agent_skill_loop.interface_design.runtime import evaluate_frozen_interface_solver
from agent_skill_loop.interface_design.session_baseline import load_dev_or_public_suite
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

    @staticmethod
    def _session_has_provider_terminal(session_dir: Path) -> bool:
        db_path = session_dir / "session.sqlite3"
        if not db_path.is_file():
            return False
        con = sqlite3.connect(str(db_path), timeout=10.0)
        try:
            row = con.execute(
                "SELECT 1 FROM tasks WHERE terminal_reason='PROVIDER_TERMINAL' LIMIT 1"
            ).fetchone()
            return row is not None
        except sqlite3.Error:
            return False
        finally:
            con.close()

    def ensure_initialized(self) -> dict[str, Any]:
        if (self.session_dir / "session.sqlite3").is_file():
            state = read_state(run=self.session_dir)
            rem = self.budget.remaining
            if (
                state.get("run_state") in {"COMPLETED", "FAILED", "STOPPED"}
                and self._session_has_provider_terminal(self.session_dir)
                and (rem is None or rem > 0)
            ):
                archive_path = self.run_dir / f"session_run_interrupted_{int(time.time() * 1000)}"
                shutil.move(str(self.session_dir), str(archive_path))
            else:
                return state
        eoh_endpoint = "mock://local" if self.config.mode == "mock" else self.config.endpoint
        eff_solver_timeout = max(
            float(self.config.candidate_timeout_s),
            derive_effective_batch_timeout_s(
                max(12, int(self.config.dev_instance_count)),
                float(self.config.instance_time_budget_ms),
                floor_s=float(self.config.candidate_timeout_s),
            ),
        )
        pb_cfg: dict[str, Any] = {
            "ledger_path": str(self.budget.ledger_path),
            "max_requests": self.budget.max_requests,
            "run_id": self.budget.run_id,
            "strict_checkpoint_barriers": bool(self.config.strict_checkpoint_barriers),
        }
        if getattr(self.budget, "owner_epoch", None):
            pb_cfg["owner_epoch"] = self.budget.owner_epoch
        init_kwargs: dict[str, Any] = {
            "output": self.session_dir,
            "operation_id": f"init_{self.config.run_id}",
            "eoh_model": self.config.eoh_model,
            "eoh_endpoint": eoh_endpoint,
            "eoh_api_key_env": self.config.api_key_env,
            "eoh_max_requests": self.config.total_request_cap,
            "eoh_round_max_requests": None,
            "engine_wall_seconds": self.config.wall_seconds,
            "solver_timeout": eff_solver_timeout,
            "request_timeout": self.config.request_timeout_s,
            "memory_enabled": False,
            "agent_guidance": bool(self.config.agent_guidance),
            "seed": self.config.search_seed,
            "max_rounds": max(1, int(self.config.max_rounds)),
            "search_policy_defaults": {
                "pop_size": self.config.eoh_pop_size,
                "n_pop": self.config.eoh_n_pop,
                "max_sample_nums": self.config.eoh_max_sample_nums,
            },
            "persistent_budget": pb_cfg,
        }
        if self.config.eoh_pop_size > 8 or self.config.eoh_n_pop > 5 or self.config.eoh_max_sample_nums > 16:
            init_kwargs["search_policy_limits"] = {
                "pop_size": [2, max(8, int(self.config.eoh_pop_size))],
                "n_pop": [1, max(5, int(self.config.eoh_n_pop))],
                "max_sample_nums": [1, max(16, int(self.config.eoh_max_sample_nums))],
            }
        if self.config.model_routing_policy is not None:
            init_kwargs["model_routing"] = dict(self.config.model_routing_policy)
        if self.config.use_benchmark_dev_suite:
            init_kwargs["benchmark_id"] = BENCHMARK_ID
            init_kwargs["benchmark_profile_name"] = self.config.dev_suite_id
            init_kwargs["round_budget"] = max(32, int(self.config.eoh_max_sample_nums) * 2 + 32)
        else:
            init_kwargs["count"] = self.config.dev_instance_count
            init_kwargs["size"] = self.config.dev_instance_size
        return initialize_session(**init_kwargs)

    @staticmethod
    def _extract_obj(record: Mapping[str, Any]) -> float | None:
        if not record.get("valid"):
            return None
        for key in ("objective", "tour_length", "bins_used"):
            val = record.get(key)
            if val is not None and not isinstance(val, bool) and isinstance(val, (int, float)):
                return float(val)
        return None

    def _evaluate_frozen_on_dev(self, frozen_solver: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if frozen_solver is None:
            return None
        assert_milestone_suite_allowed_for_interactive_role(self.config.dev_suite_id, role="diagnostic_interactive")
        suite = load_dev_or_public_suite(self.config.dev_suite_id, split=self.config.dev_split, role="diagnostic_interactive")
        assert_milestone_suite_allowed_for_interactive_role(self.config.dev_suite_id, suite, role="diagnostic_interactive")
        fs = FrozenInterfaceSolver.from_dict(frozen_solver)
        dist_conv = str(suite.get("distance_convention") or "not_applicable")
        veh_pol = str(suite.get("vehicle_limit_policy") or "not_applicable")
        outer_s = max(5.0, float(self.config.instance_time_budget_ms) / 1000.0 + 3.0)
        dev_records = [
            evaluate_frozen_interface_solver(
                fs,
                inst,
                distance_convention=dist_conv,
                vehicle_limit_policy=veh_pol,
                solve_deadline_ms=self.config.instance_time_budget_ms,
                outer_timeout_s=outer_s,
                protocol_id=suite.get("protocol_id"),
            )
            for inst in suite["instances"]
        ]
        valid_objs: list[float] = []
        penalized_objs: list[float] = []
        for inst, rec in zip(suite["instances"], dev_records):
            obj = self._extract_obj(rec)
            if obj is not None:
                valid_objs.append(obj)
                penalized_objs.append(obj)
            else:
                ref_obj = inst.get("reference_objective")
                penalty = 2.0 * float(ref_obj) if isinstance(ref_obj, (int, float)) and float(ref_obj) > 0 else 100.0
                penalized_objs.append(penalty)
        solve_times = [float(r["solve_ms"]) for r in dev_records if r.get("solve_ms") is not None]
        n_total = len(dev_records)
        valid_count = len(valid_objs)
        comp_rate = round(valid_count / max(1, n_total), 6)
        valid_only_mean = round(sum(valid_objs) / valid_count, 6) if valid_objs else None
        pen_mean = round(sum(penalized_objs) / max(1, n_total), 6)
        return {
            "suite_id": self.config.dev_suite_id,
            "protocol_id": suite.get("protocol_id"),
            "valid_count": valid_count,
            "instance_count": n_total,
            "completion_rate": comp_rate,
            "all_feasible": bool(n_total > 0 and valid_count == n_total),
            "failure_penalty_policy": "2x_reference_objective",
            "valid_only_mean_objective": valid_only_mean,
            "penalized_mean_objective": pen_mean,
            "mean_objective": pen_mean,
            "valid_only_mean_tour_length": valid_only_mean,
            "penalized_mean_tour_length": pen_mean,
            "mean_tour_length": pen_mean,
            "solve_ms_mean": round(sum(solve_times) / len(solve_times), 4) if solve_times else None,
            "records": dev_records,
        }

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

        target_round = int(round_id)
        cur_round = int(st.get("round_id") or 1)
        round_state = str(st.get("state") or "")
        ver = int(st["state_version"])

        # Crash-resume alignment: if Session already committed target_round and moved to cur_round > target_round
        # (or already finalized target_round cleanly), recover target_round's exact artifacts without touching cur_round.
        target_eval_path = self.session_dir / "rounds" / f"round_{target_round:04d}" / "evaluation_facts.json"
        if target_eval_path.is_file() and (
            cur_round > target_round
            or (cur_round == target_round and st.get("run_state") in {"COMPLETED", "STOPPED", "FAILED"} and round_state == "ROUND_COMPLETED")
        ):
            ev_facts_rec = json.loads(target_eval_path.read_text(encoding="utf-8")) if target_eval_path.is_file() else {}
            f_ref = ev_facts_rec.get("frozen_solver_ref")
            frozen_rec = json.loads((self.session_dir / f_ref).read_text(encoding="utf-8")) if (f_ref and (self.session_dir / f_ref).is_file()) else None
            dev_eval_rec = self._evaluate_frozen_on_dev(frozen_rec) if eval_dev_suite else None
            return {
                "round_id": target_round,
                "session_status": st.get("run_state") or "already_completed",
                "round_state": "ROUND_COMPLETED",
                "evaluation_facts": ev_facts_rec,
                "frozen_solver": frozen_rec,
                "dev_eval": dev_eval_rec,
                "crossed_checkpoints": [],
                "requests_before": prev_used,
                "requests_after": prev_used,
                "recovered_completed_round": True,
            }

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

        terminal_reason = ""
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
                        terminal_reason = str((col.get("result") or {}).get("terminal_reason") or "")
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

        if terminal_reason == "PROVIDER_TERMINAL":
            if round_state == "READY_TO_FINISH":
                finish_round(
                    run=self.session_dir,
                    operation_id=f"fin_r{cur_round}_{self.config.run_id}",
                    expected_state_version=int(st["state_version"]),
                    decision="complete",
                )
            eoh_sum_path = self.session_dir / f"rounds/round_{cur_round:04d}/eoh_run/summary.json"
            prov_err = "provider_terminal"
            if eoh_sum_path.is_file():
                try:
                    eoh_sum = json.loads(eoh_sum_path.read_text(encoding="utf-8"))
                    prov_err = str(eoh_sum.get("provider_error_code") or eoh_sum.get("stop_reason") or prov_err)
                except (OSError, json.JSONDecodeError):
                    pass
            raise ProviderFailure(f"session_provider_terminal:{prov_err}")

        if terminal_reason in {"STARTUP_FAILED", "EVIDENCE_STORAGE_FAILED"} or st.get("run_state") == "FAILED":
            raise RuntimeError(f"session_task_terminal:{terminal_reason or st.get('run_state')}")

        if round_state == "READY_TO_FINISH":
            if self._session_has_provider_terminal(self.session_dir):
                finish_round(
                    run=self.session_dir,
                    operation_id=f"fin_r{cur_round}_{self.config.run_id}",
                    expected_state_version=int(st["state_version"]),
                    decision="complete",
                )
                raise ProviderFailure("session_provider_terminal:ready_to_finish_resume")
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

        dev_eval = self._evaluate_frozen_on_dev(frozen_solver) if eval_dev_suite else None

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
