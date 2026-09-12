"""Supervised upstream runner. No operator replacement or provider credentials."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from agent_skill_loop.skill_store import _atomic_write_text


def main() -> int:
    from eoh import EoH, LLMConfig
    from eoh.config import EoHConfig
    from agent_skill_loop.problems.base import get_problem
    from eoh_frozen.problem import FrozenProblem

    root = Path(sys.argv[1])
    cfg = json.loads((root / "worker_config.json").read_text(encoding="utf-8"))
    result = {"status": "completed"}
    try:
        suite = json.loads((root / "dev_suite.json").read_text(encoding="utf-8"))
        task = FrozenProblem(suite, spec=get_problem(cfg["problem"]), timeout=cfg["solver_timeout"],
                             deadline=cfg["deadline"], origin="engine",
                             round_context=cfg.get("round_context"),
                             evaluation_log=root / "results/evaluations.jsonl",
                             fail_log=root / "results/eval_failures.jsonl")
        llm = LLMConfig(use_local=True, local_url=cfg["local_url"], timeout=cfg["request_timeout"] + 5)
        engine_kwargs = dict(
            llm=llm, problem=task, pop_size=cfg["pop_size"], n_pop=cfg["n_pop"],
            operators=cfg["operators"], max_sample_nums=cfg["max_sample_nums"],
            num_samplers=1, num_evaluators=1, use_seed=cfg["use_seed"],
            seed_path=str(root / "seeds/parent_skill.json"), output_dir=str(root),
        )
        repair_engine = cfg.get("repair_mode") == "bounded"
        if repair_engine:
            from eoh_frozen.repair import LocalRepairRequester, RepairingEOH
            engine_config = EoHConfig(**{key: value for key, value in engine_kwargs.items() if key != "problem"})
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
            engine = EoH(**engine_kwargs)
        engine.run()
        if repair_engine:
            _atomic_write_text(root / "results/repair_summary.json", json.dumps(engine.repair_summary(), ensure_ascii=False))
    except Exception as exc:
        result = {"status": "engine_failed", "error_type": type(exc).__name__,
                  "error_code": "no_valid_initial_population" if str(exc).startswith("Initial population is empty.") else "engine_exception"}
        if 'engine' in locals() and hasattr(engine, "repair_summary"):
            try:
                _atomic_write_text(root / "results/repair_summary.json", json.dumps(engine.repair_summary(), ensure_ascii=False))
            except OSError:
                pass
    _atomic_write_text(root / "worker_result.json", json.dumps(result))
    return 0 if result["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
