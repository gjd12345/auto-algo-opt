"""Focused state/ledger tests; fixture physics is covered by verify_session."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from artifact_session import ledger, runtime, supervisor
from artifact_session.store import DDL, SessionError, connect, dumps, record
from optics_backend.artifacts import canonical, digest, save
import time


class SessionContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.run = Path(self.temp.name)
        self.conf = {"global_deadline": time.time() + 100, "search_deadline": time.time() + 80,
                     "audit_capacity_partition": 8, "budgets": {"max_generation_requests": 2,
                     "max_candidate_attempts": 2, "max_online_assessments": 3, "max_profile_executions": 11,
                     "max_audit_assessments": 2, "max_rounds": 4}}
        with connect(self.run) as db:
            db.executescript(DDL)
            db.execute("INSERT INTO run(id,config,config_hash,state,version,round) VALUES(1,?,?,'SEARCHING',1,1)",
                       (dumps(self.conf), digest(canonical(self.conf))))
            db.execute("INSERT INTO rounds(id,state) VALUES(1,'READY_TO_FINISH')")

    def tearDown(self):
        self.temp.cleanup()

    def test_capacity_is_not_effect_and_generation_is_bounded(self):
        with connect(self.run) as db:
            self.assertEqual(ledger.counts(db)["AUDIT_PROFILE"], 0)
        for i in range(2):
            ledger.reserve_generation(self.run, str(i), 1, {})
        with self.assertRaisesRegex(SessionError, "BUDGET"):
            ledger.reserve_generation(self.run, "3", 1, {})
        with connect(self.run) as db:
            self.assertEqual(ledger.counts(db)["MODEL_REQUEST"], 2)

    def test_reuse_requires_full_identity_and_no_profile_reservation(self):
        from artifact_session.runner import reusable_online
        identity={"mode":"online","canonical_artifact_sha256":"same", "environment_manifest_hash":"env1"}
        ref={"assessment_id":"a", "directory":"assessments/a", "facts_sha256":"facts"}
        with connect(self.run) as db:
            db.execute("INSERT INTO assessments(id,round,mode,state,artifact,facts,sequence) VALUES('a',1,'online','COMPLETE','a',?,1)", (dumps(ref),))
        with patch("artifact_session.runner.facts_for",return_value={"evaluation_identity":identity}):
            self.assertEqual(reusable_online(self.run,identity)[0],ref)
            self.assertEqual(reusable_online(self.run,{**identity,"environment_manifest_hash":"env2"}),(None,None))
        with connect(self.run) as db:
            self.assertEqual(ledger.counts(db)["ONLINE_PROFILE"],0)

    def test_recovery_blocks_live_physics_child(self):
        save(self.run / "assessments/a/process_owner.json", {"pid": 42, "birth": "child"})
        with patch("artifact_session.supervisor.process_birth", return_value="child"):
            with self.assertRaisesRegex(SessionError, "CHILD_PROCESS_STILL_RUNNING"):
                supervisor.recover(self.run, "recover", 1)
        with connect(self.run) as db:
            self.assertEqual(record(db)["version"], 1)

    def test_next_round_has_fresh_budget(self):
        result = runtime.finish_round(self.run, "continue", "finish", 1)
        self.assertEqual(result["next_round"], 2)
        self.assertEqual(runtime.finish_round(self.run, "continue", "finish", 1), result)
        with self.assertRaisesRegex(SessionError, "OPERATION_ID_CONFLICT"):
            runtime.finish_round(self.run, "complete", "finish", 1)

    def test_two_round_memory_host_fixture(self):
        from artifact_session.store import evidence
        self.conf["memory_enabled"] = True
        self.conf["task_contract_hash"] = "fixture-task"
        self.conf["controller_contract_hash"] = "fixture-controller"
        with connect(self.run) as db:
            db.execute("UPDATE run SET config=?,config_hash=?", (dumps(self.conf),digest(canonical(self.conf))))
            facts_ref=evidence(self.run,"rounds/0001/online_facts.json",{"round_id":1,"candidates":[]})
            db.execute("UPDATE rounds SET state='WAITING_FOR_EVALUATION',facts=? WHERE id=1",(dumps(facts_ref),))
        value={"schema_id":"optical-prescription-evaluation/v1","round_id":1,
               "online_facts_ref":facts_ref,"plan_alignment":"unknown","observations":[],
               "hypotheses":[],"next_search_advice":"fixture","memory_action":"insight"}
        runtime.submit_evaluation(self.run,value,"eval",1)
        with self.assertRaisesRegex(SessionError,"MEMORY_PUBLICATION_PENDING"):
            runtime.finish_round(self.run,"continue","blocked",2)
        runtime.memory_write(self.run,{"id":"fixture","kind":"insight","summary":"bounded observation",
            "body":"Fixture only; no physics claim", "based_on":None,"evidence_ref":facts_ref},"write",2)
        runtime.finish_round(self.run,"continue","next",3)
        entry=runtime.memory_read(self.run,"fixture")[0]
        self.assertEqual(entry["body"]["body"],"Fixture only; no physics claim")
        self.assertEqual(runtime.state(self.run)["round_id"],2)

    def test_unknown_process_blocks_effects(self):
        effect = ledger.reserve_generation(self.run, "1", 1, {})
        ledger.start_effect(self.run, effect)
        ledger.finish_effect(self.run, effect, "UNKNOWN", {"process_confirmed_dead": False})
        with self.assertRaisesRegex(SessionError, "UNKNOWN_PROCESS"):
            ledger.reserve_generation(self.run, "2", 1, {})

    def test_audit_four_reservations_and_no_replay(self):
        with connect(self.run) as db:
            db.execute("UPDATE run SET state='FINALIZING'")
        assessment = ledger.reserve_assessment(self.run, 1, "audit", "artifact")
        with connect(self.run) as db:
            self.assertEqual(ledger.counts(db)["AUDIT_PROFILE"], 4)
        ledger.start_effect(self.run, assessment + "-0")
        ledger.finish_effect(self.run, assessment + "-0", "UNKNOWN", {"process_confirmed_dead": True})
        with self.assertRaisesRegex(SessionError, "ALREADY_STARTED"):
            ledger.start_effect(self.run, assessment + "-0")
        ledger.reserve_assessment(self.run, 1, "audit", "other")
        with self.assertRaisesRegex(SessionError, "AUDIT_BUDGET"):
            ledger.reserve_assessment(self.run, 1, "audit", "third")

    def test_recovery_never_kills_reused_pid_or_replays(self):
        with connect(self.run) as db:
            db.execute("INSERT INTO tasks(id,round,purpose,state,pid,birth) VALUES('t',1,'search','RUNNING',42,'old')")
        with patch("artifact_session.supervisor.process_birth", return_value="new"):
            with self.assertRaisesRegex(SessionError, "PID_IDENTITY"):
                supervisor.terminate_owned({"pid": 42, "birth": "old"})
        effect = ledger.reserve_generation(self.run, "one", 1, {})
        ledger.start_effect(self.run, effect)
        with patch("artifact_session.supervisor.process_birth", return_value=None), patch("artifact_session.runtime.seal") as seal:
            supervisor.recover(self.run, "recover", 1)
            seal.assert_called_once()
        with connect(self.run) as db:
            item = db.execute("SELECT * FROM effects WHERE id=?", (effect,)).fetchone()
            self.assertEqual(item["state"], "UNKNOWN")
            self.assertTrue(json.loads(item["detail"])["process_confirmed_dead"])


if __name__ == "__main__":
    unittest.main()
