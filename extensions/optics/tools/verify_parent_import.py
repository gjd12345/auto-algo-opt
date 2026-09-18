"""Focused real-physics, zero-provider continuation regression."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from verify_session import config_for, plan_for, mutate, wait
from artifact_session import runtime
from artifact_session.parent_import import freeze_parent, accepted_receipt
from artifact_session.recovery import reconcile_completed
from artifact_session.report import build
from artifact_session.store import SessionError, connect, read, transaction
from optics_backend.artifacts import canonical, digest, save


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--assessment", required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    conf = json.loads((a.source / "config.json").read_bytes())
    facts = json.loads((a.source / "assessments" / a.assessment / "facts.json").read_bytes())
    seed = {"source_run": str(a.source.resolve()), "assessment_id": a.assessment,
            "facts_sha256": digest(canonical(facts)),
            "canonical_artifact_sha256": facts["evaluation_identity"]["canonical_artifact_sha256"]}
    frozen = freeze_parent(seed, conf["task_contract_hash"])
    try:
        freeze_parent({**seed, "facts_sha256": "0" * 64}, conf["task_contract_hash"])
    except SessionError:
        pass
    else:
        raise AssertionError("CORRUPT_PARENT_ACCEPTED")
    bundle = Path(conf["bundle"])
    baseline_hash = digest((bundle / "assets/initial_prescription.json").read_bytes())
    raw = config_for(bundle, conf["task_contract_hash"],
                     [canonical({"description": "fixture parent tie", "prescription": frozen["prescription"]}).decode()])
    raw["online_parent"] = seed
    raw["budgets"]["max_online_assessments"] = 6
    raw["budgets"]["max_profile_executions"] = 14
    runtime.initialize(a.output, raw)
    mutate(runtime.submit_plan, a.output, plan_for(raw, 1), op="parent-plan")
    mutate(runtime.launch, a.output, "search", op="parent-execute")
    wait(a.output)
    result = runtime.read_evaluation(a.output, 1)
    request = read(a.output, result["facts"]["candidates"][0]["request_ref"])
    assert request["context"]["parent_prescription"] == frozen["prescription"]
    assert runtime.state(a.output)["counts"]["ONLINE_PROFILE"] == 2
    assert result["facts"]["candidates"][0]["evaluation_reused_from"]
    with transaction(a.output) as db:
        receipt = accepted_receipt(db)
        assert receipt and receipt["new_discovery"] is False
        before = db.execute("SELECT COUNT(*) FROM effects").fetchone()[0]
        reconcile_completed(db, a.output)
        reconcile_completed(db, a.output)
        assert db.execute("SELECT COUNT(*) FROM effects").fetchone()[0] == before
        assert accepted_receipt(db) == receipt
    summary, _ = build(a.output)
    assert summary["external_requests"] == 0
    assert summary["online_profile_roles"] == {"baseline": 1, "inherited_parent": 1}
    assert digest((bundle / "assets/initial_prescription.json").read_bytes()) == baseline_hash
    save(a.output / "parent_import_receipt.json", {"passed": True, "counts": summary["counts"],
         "roles": summary["online_profile_roles"], "external_requests": 0, "online_parent": receipt})
    print("PASS: parent import/reassessment/prompt/accounting/recovery; zero provider requests")


if __name__ == "__main__":
    main()
