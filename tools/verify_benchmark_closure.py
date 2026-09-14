"""Zero-paid-API Session-to-report acceptance probe using official EoH."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_skill_loop import session_actions as actions, session_runtime as db
from agent_skill_loop.benchmark import (
    ExperimentManifest, FrozenSelection, PopulationSnapshot, benchmark_profile,
    build_archive_from_session, build_report, evaluate_selection, freeze_selection,
    load_profile_suite,
)
from eoh_frozen.smoke import fixture_provider
from agent_skill_loop.skill_store import load_skill


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def reachable_bins(instance):
    states = {()}
    for item in instance["items"]:
        following = set()
        for bins in states:
            feasible = [i for i, remaining in enumerate(bins) if remaining >= item]
            if not feasible:
                following.add(tuple(sorted((*bins, instance["capacity"] - item))))
            for index in feasible:
                updated = list(bins)
                updated[index] -= item
                following.add(tuple(sorted(updated)))
        states = following
    return sorted({len(bins) for bins in states})


def main(output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    root = output / "session"
    key = "BENCHMARK_CLOSURE_FIXTURE_KEY"
    previous = os.environ.get(key)
    os.environ[key] = "localhost-fixture"
    try:
        def responder(prompt, index):
            if prompt == "1+1=?":
                return 200, "2"
            # Alternate First Fit and Best Fit on the non-degenerate suite.
            # Scores still come exclusively from the production evaluator.
            expression = "np.zeros_like(bins)" if index % 2 else "-bins"
            code = f"def priority(item, bins):\n    fixture_revision = {index}\n    return {expression}\n"
            return 200, "{Deterministic fixture heuristic}\n```python\n" + code + "```"

        with fixture_provider("obp_online", responder=responder) as (endpoint, prompts):
            db.initialize_session(
                output=root, operation_id="init", eoh_model="fixture", eoh_endpoint=endpoint,
                eoh_api_key_env=key, benchmark_id="eohs_v1", benchmark_profile_name="obp_evolution_mini",
                inheritance_mode="population_seeds", agent_guidance=False,
                max_rounds=2, max_solver_calls=20, round_budget=10,
                search_policy_defaults={"pop_size": 2, "n_pop": 2, "max_sample_nums": 20},
                search_policy_limits={"pop_size": [2, 2], "n_pop": [2, 2], "max_sample_nums": [20, 20]},
                eoh_max_requests=40, engine_wall_seconds=120, round_wall_seconds=60,
            )
            rounds = []
            for number in (1, 2):
                state = db.read_state(run=root)
                plan_path = output / f"plan_{number}.json"
                save(plan_path, dict(round_id=number, direction="Neutral fixture acceptance",
                    operations=[dict(type="preserve", target="interface", mechanism="Preserve problem contract")],
                    preserve="Frozen evaluator and interface", hypothesis="Fixture wiring only",
                    feedback_basis=state["feedback_basis"], memory_basis=[]))
                planned = actions.submit_plan(run=root, operation_id=f"plan-{number}",
                    expected_state_version=state["state_version"], file=plan_path)
                launched = actions.execute(run=root, operation_id=f"execute-{number}",
                    expected_state_version=planned["state_version"])
                if launched["run_state"] == "FAILED":
                    rounds.append(launched)
                    break
                deadline = time.monotonic() + 75
                while time.monotonic() < deadline:
                    state = db.read_state(run=root)
                    if state["task"]["state"] == "EXITED":
                        break
                    time.sleep(.1)
                else:
                    raise RuntimeError("fixture_supervisor_did_not_settle")
                collected = actions.collect(run=root, operation_id=f"collect-{number}",
                    expected_state_version=state["state_version"])
                facts = actions.read_evaluation(run=root)["result"]
                rounds.append(facts)
                evaluation_path = output / f"evaluation_{number}.json"
                save(evaluation_path, dict(plan_alignment="unknown", observations=[dict(
                    claim="Fixture produced deterministic evaluation facts; no algorithm-effect claim.",
                    evidence_refs=facts["evidence_refs"][:1])], hypotheses=[], next_search_advice={},
                    memory_action={"kind": "disabled"}))
                evaluated = actions.submit_evaluation(run=root, operation_id=f"evaluate-{number}",
                    expected_state_version=collected["state_version"], file=evaluation_path)
                actions.finish_round(run=root, operation_id=f"finish-{number}",
                    expected_state_version=evaluated["state_version"], decision="continue" if number == 1 else "complete")
            local_requests = len(prompts)
        archive = build_archive_from_session(root)
        assert archive["entries"], "production facts must yield generated archive entries"
        assert all(x["origin"] in {"generated", "generated_repair"} for x in archive["entries"])
        assert len({x["code_sha256"] for x in archive["entries"]}) == archive["entry_count"]
        save(output / "archive.json", archive)
        config = json.loads((root / "config_frozen.json").read_text(encoding="utf-8"))
        manifest_raw = config["experiment_manifest"]
        # The frozen Session stores the full document separately from its hash.
        manifest_data = manifest_raw.get("document", manifest_raw.get("manifest", manifest_raw))
        if "benchmark_spec_hash" not in manifest_data:
            raise ValueError("manifest_document_missing")
        manifest = ExperimentManifest(**{k: v for k, v in manifest_data.items() if k not in {"schema_version", "sha256", "experiment_manifest_sha256"}})
        assert len(rounds) == 2 and rounds[-1].get("run_state") != "FAILED", "two_round_search_required"
        assert rounds[1]["dual_budget"]["seed_reevaluation_attempts"] >= 2
        first_snapshot = PopulationSnapshot.from_dict(json.loads(
            (root / "rounds/round_0001/population_snapshot.json").read_text(encoding="utf-8")))
        assert len({member["objective"] for member in first_snapshot.members}) >= 2
        assert any(row["origin"] == "generated" for row in rounds[1]["candidates"])
        _benchmark, metric, _ = benchmark_profile("eohs_v1", "obp_evolution_mini")
        snapshot_path = root / "rounds/round_0002/population_snapshot.json"
        snapshot = PopulationSnapshot.from_dict(json.loads(snapshot_path.read_text(encoding="utf-8")))
        reports = []
        for kind in ("incumbent_top1", "archive_topk", "final_population_set"):
            selected = freeze_selection(kind, archive["entries"], metric_spec_hash=metric.content_hash,
                k=10 if kind == "archive_topk" else None, population_snapshot=snapshot,
                source_ref="archive.json" if kind != "final_population_set" else str(snapshot_path.relative_to(output)))
            if kind == "incumbent_top1":
                incumbent = rounds[-1]["incumbent_after"]
                skill = load_skill(root / incumbent["ref"])
                selected = FrozenSelection(selection_kind=kind,
                    members=({"code": skill.code, "code_sha256": skill.code_sha256,
                              "objective": skill.mean_objective, "origin": skill.origin},),
                    training_metric_spec_hash=metric.content_hash, source_ref=incumbent["ref"])
            selection_path = output / f"{kind}.selection.json"
            save(selection_path, {**selected.as_dict(), "content_hash": selected.content_hash})
            selected = FrozenSelection.from_dict(json.loads(selection_path.read_text(encoding="utf-8")))
            test = evaluate_selection(selected, load_profile_suite("eohs_v1", "obp_evolution_mini", split="heldout"))
            identity = dict(experiment_manifest_sha256=manifest.content_hash, selection_sha256=selected.content_hash)
            budget = {**db.read_state(run=root)["result"]["budgets"], **identity}
            metrics = {**identity, "metric_spec_hash": metric.content_hash,
                       "best_training_fitness": min(x["objective"] for x in selected.members)}
            inputs = dict(manifest=manifest.as_dict(), selection={**selected.as_dict(), "content_hash": selected.content_hash},
                          metrics=metrics, budget=budget, test_result=test)
            save(output / f"{kind}.inputs.json", inputs)
            persisted = json.loads((output / f"{kind}.inputs.json").read_text(encoding="utf-8"))
            persisted["manifest"] = ExperimentManifest(**{k: v for k, v in persisted["manifest"].items() if k != "schema_version"})
            persisted["selection"] = FrozenSelection.from_dict(persisted["selection"])
            report = build_report(**persisted)
            save(output / f"{kind}.report.json", report)
            reports.append(f"{kind}.report.json")
        assert build_archive_from_session(root) == archive
        con = db._connect(root / "session.sqlite3")
        try:
            ledger = [dict(x) for x in con.execute("SELECT * FROM solver_calls")]
            assert len({x["evaluation_id"] for x in ledger}) == len(ledger)
            assert con.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == local_requests
        finally:
            con.close()
        save(output / "pilot_receipt.json", dict(
            status="blocked" if len(rounds) < 2 or rounds[-1].get("run_state") == "FAILED" else "passed",
            external_provider_requests=0, localhost_fixture_requests=local_requests,
            rounds=rounds, reports=reports, reload_verified=True,
            reachable_bins=[dict(instance_id=x["instance_id"], bins=reachable_bins(x))
                            for x in load_profile_suite("eohs_v1", "obp_evolution_mini")["instances"]]))
        hashes = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in output.rglob("*") if p.is_file() and not p.name.endswith(("-wal", "-shm"))}
        save(output / "sha256_manifest.json", hashes)
        assert all(hashlib.sha256((output / name).read_bytes()).hexdigest() == expected
                   for name, expected in json.loads((output / "sha256_manifest.json").read_text()).items())
        print(json.dumps(dict(output=str(output), reports=reports, external_provider_requests=0,
                              status=json.loads((output / "pilot_receipt.json").read_text())["status"])))
        return 0 if json.loads((output / "pilot_receipt.json").read_text())["status"] == "passed" else 1
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(main(parser.parse_args().output))
