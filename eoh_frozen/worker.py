"""Supervised upstream runner. No operator replacement or provider credentials."""
from __future__ import annotations

import json
import hashlib
import random
import sys
from pathlib import Path

from agent_skill_loop.skill_store import _atomic_write_text


def main() -> int:
    from eoh import LLMConfig
    from eoh.config import EoHConfig
    from agent_skill_loop.problems.base import get_problem
    from eoh_frozen.problem import FrozenProblem
    from eoh_frozen.provenance import ProvenanceEOH

    root = Path(sys.argv[1])
    cfg = json.loads((root / "worker_config.json").read_text(encoding="utf-8"))
    if cfg.get("supervisor_pid"):
        import threading
        from agent_skill_loop.eval_worker import _watch_parent
        threading.Thread(target=_watch_parent,args=(cfg["supervisor_pid"],),daemon=True).start()
    result = {"status": "completed"}
    try:
        suite = json.loads((root / "dev_suite.json").read_text(encoding="utf-8"))
        seed_bindings = None
        seed_path = Path(str(cfg.get("seed_path") or root / "seeds/parent_skill.json"))
        if int(cfg.get("population_seed_count", 0) or 0) > 0:
            try:
                seed_payload = json.loads(seed_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("population_seed_file_invalid") from exc
            if not isinstance(seed_payload, list):
                raise ValueError("population_seed_file_invalid")
            seed_bindings = {}
            for index, item in enumerate(seed_payload):
                if not isinstance(item, dict) or not isinstance(item.get("code"), str) or not item["code"].strip():
                    raise ValueError("population_seed_file_invalid")
                code = item["code"]
                code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
                if item.get("code_sha256") is not None and item["code_sha256"] != code_hash:
                    raise ValueError("population_seed_code_hash_mismatch")
                if code_hash in seed_bindings:
                    raise ValueError("population_seed_duplicate_code")
                seed_bindings[code_hash] = {
                    "origin": "population_seed",
                    "candidate_id": f"seed_{index + 1}",
                    "revision": "original",
                    "seed_index": index,
                    "source_candidate_id": item.get("candidate_id"),
                    "source_evaluation_id": item.get("evaluation_id"),
                    "source_ref": item.get("source_ref"),
                }
            if len(seed_bindings) != int(cfg.get("population_seed_count", 0) or 0):
                raise ValueError("population_seed_count_mismatch")
        task = FrozenProblem(suite, spec=get_problem(cfg["problem"]), timeout=cfg["solver_timeout"],
                             deadline=cfg["deadline"], origin="engine",
                             round_context=cfg.get("round_context"),
                             session=cfg.get("session"),
                             metric_spec_hash=cfg.get("metric_spec_hash"),
                             data_manifest_hash=cfg.get("data_manifest_hash"),
                             problem_spec_hash=cfg.get("problem_spec_hash"),
                             seed_bindings=seed_bindings,
                             evaluation_log=root / "results/evaluations.jsonl",
                             fail_log=root / "results/eval_failures.jsonl")
        llm = LLMConfig(use_local=True, local_url=cfg["local_url"], timeout=cfg["request_timeout"] + 5)
        engine_kwargs = dict(
            llm=llm, problem=task, pop_size=cfg["pop_size"], n_pop=cfg["n_pop"],
            operators=cfg["operators"], max_sample_nums=cfg["max_sample_nums"],
            num_samplers=1, num_evaluators=1, use_seed=cfg["use_seed"],
            seed_path=str(cfg.get("seed_path") or root / "seeds/parent_skill.json"), output_dir=str(root),
        )
        repair_engine = cfg.get("repair_mode") == "bounded"
        engine_config = EoHConfig(**{key: value for key, value in engine_kwargs.items() if key != "problem"})
        if repair_engine:
            from eoh_frozen.repair import LocalRepairRequester, RepairingEOH
            engine = RepairingEOH(
                engine_config,
                task,
                repair_request=LocalRepairRequester(
                    cfg["local_url"], deadline=cfg["deadline"], timeout=cfg["request_timeout"]
                ),
                max_repairs_per_candidate=cfg.get("max_repairs_per_candidate", 1),
                max_repair_requests_total=cfg.get("max_repair_requests_total"),
            )
        else:
            # ``EoH.run()`` constructs the internal EOH object and resets the
            # module-level RNG to a literal upstream seed immediately before
            # search.  Construct that same pinned engine directly so the
            # Session's recorded search seed actually controls operator and
            # parent-selection randomness in both modes.
            engine = ProvenanceEOH(engine_config, task)
        # The pinned upstream constructor resets Python's global RNG to a
        # literal seed.  Apply the frozen Session/search seed immediately
        # after construction so operator choice and other engine randomness
        # are part of the recorded experiment identity.
        search_seed = cfg.get("search_seed")
        if search_seed is not None:
            random.seed(int(search_seed))
            try:
                import numpy as np
                np.random.seed(int(search_seed) % (2 ** 32))
            except (ImportError, ValueError):
                pass
        engine.run()
        if repair_engine:
            _atomic_write_text(root / "results/repair_summary.json", json.dumps(engine.repair_summary(), ensure_ascii=False))
    except Exception as exc:
        message = str(exc)
        if message == "round_budget_exhausted":
            result = {"status": "budget_exhausted", "stop_reason": "round_budget_limit",
                      "error_type": type(exc).__name__, "error_code": message}
        elif message == "solver_budget_exhausted":
            result = {"status": "budget_exhausted", "stop_reason": "solver_call_limit",
                      "error_type": type(exc).__name__, "error_code": message}
        else:
            result = {"status": "engine_failed", "error_type": type(exc).__name__,
                      "error_code": "no_valid_initial_population" if message.startswith("Initial population is empty.") else "engine_exception"}
        if 'engine' in locals() and hasattr(engine, "repair_summary"):
            try:
                _atomic_write_text(root / "results/repair_summary.json", json.dumps(engine.repair_summary(), ensure_ascii=False))
            except OSError:
                pass
    _atomic_write_text(root / "worker_result.json", json.dumps(result))
    return 0 if result["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
