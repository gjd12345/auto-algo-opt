"""Read-only evidence reload; no provider or physics invocation."""
import argparse
import json
from pathlib import Path
from artifact_session.store import config, connect, read
from artifact_session.report import build
from optics_backend.artifacts import canonical, digest
from optics_backend.offline import reload_facts


def verify(run):
    with connect(run) as db:
        conf = config(db)
        prior = None
        events = 0
        for row in db.execute("SELECT * FROM events ORDER BY sequence"):
            value = {"time": row["time"], "kind": row["kind"], "body": json.loads(row["body"]), "previous_hash": prior}
            assert row["previous_hash"] == prior and digest(canonical(value)) == row["hash"], "EVENT_CHAIN"
            prior = row["hash"]
            events += 1
        assessments = 0
        for row in db.execute("SELECT facts FROM assessments WHERE state='COMPLETE'"):
            ref = json.loads(row[0])
            facts = reload_facts(run / ref["directory"], conf["task_contract_hash"])
            assert digest(canonical(facts)) == ref["facts_sha256"], "ASSESSMENT_HASH"
            assessments += 1
        for row in db.execute("SELECT plan,facts,evaluation FROM rounds"):
            for value in row:
                if value:
                    read(run, json.loads(value))
        for row in db.execute("SELECT ref FROM memory"):
            read(run, json.loads(row[0]))
    first, markdown = build(run)
    second, again = build(run)
    assert first == second and markdown == again, "REPORT_NONDETERMINISTIC"
    return {"run": str(run), "events_verified": events, "complete_assessments_verified": assessments,
            "report_sha256": digest(markdown.encode()), "provider_requests": 0, "physics_calls": 0,
            "effect_states": first["effect_states"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    print(json.dumps(verify(parser.parse_args().run), indent=2))
