import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from agent_skill_loop import session_runtime as db
from agent_skill_loop import session_actions as actions
from agent_skill_loop.memory.api import MemoryAPI, MemoryEntry


def init(root, **kw):
    return db.initialize_session(output=root,operation_id="init",eoh_model="fixture",size=6,count=1,**kw)


def plan(root, memory_refs=()):
    state=db.read_state(run=root)
    return dict(round_id=state["round_id"],direction="test ranking",operations=[dict(type="replace",target="ranking",mechanism="distance")],
                preserve="interface",hypothesis="unproven",memory_basis=list(memory_refs),reference_skill_ref=None,
                feedback_basis=dict(round_id=state["round_id"]-1,evaluation_ref=state["feedback_ref"],suite_hash=json.loads((root/"dev_suite.json").read_text())["content_hash"]) if state["feedback_ref"] else None)


def test_atomic_init_and_concurrent_stop(tmp_path,monkeypatch):
    root=tmp_path/"run"
    original=db._create_schema
    def broken(con):
        original(con)
        assert con.in_transaction
        raise RuntimeError("injected crash")
    monkeypatch.setattr(db,"_create_schema",broken)
    with pytest.raises(RuntimeError): init(root)
    assert not root.exists()
    monkeypatch.setattr(db,"_create_schema",original)
    init(root)
    def stop(op):
        try: return db.stop_session(run=root,operation_id=op,expected_state_version=1)["ok"]
        except db.SessionError as e: return e.code
    with ThreadPoolExecutor(2) as pool:
        outcomes=list(pool.map(stop,["a","b"]))
    assert sorted(map(str,outcomes))==["STATE_VERSION_CONFLICT","True"]


def test_memory_requires_complete_same_round_body_and_preserves_failed_submission(tmp_path):
    root=tmp_path/"run"
    memory=MemoryAPI(tmp_path/"memory")
    record=memory.write(MemoryEntry("direction","ranking","insight","cvrp_construct","select_next_node","**Why:** distance matters.\n**How to apply:** test ranking."))
    init(root,memory_store=str(memory.store))
    found=actions.memory_search(run=root)["result"]["memories"]
    assert "body" not in found[0]
    page=actions.memory_read(run=root,reference=record["reference"],limit=10)["result"]
    assert not page["complete_memory_consumption"]
    file=tmp_path/"plan.json"
    file.write_text(json.dumps(plan(root,[record["reference"]])))
    with pytest.raises(db.SessionError,match="memory_reference_not_found"):
        actions.submit_plan(run=root,operation_id="plan",expected_state_version=1,file=file)
    actions.memory_read(run=root,reference=record["reference"],offset=10)
    accepted=actions.submit_plan(run=root,operation_id="plan",expected_state_version=1,file=file)
    assert accepted["state"]=="READY_TO_EXECUTE"
    assert "distance matters" in (root/"rounds/round_0001/round_context.txt").read_text()
    assert actions.submit_plan(run=root,operation_id="plan",expected_state_version=999,file=file)==accepted


def test_audit_flush_failure_replays_without_losing_mutation(tmp_path,monkeypatch):
    root=tmp_path/"run"
    init(root)
    original=db._atomic_write
    def broken(path,text):
        if path.name=="events.jsonl": raise OSError("injected audit failure")
        original(path,text)
    monkeypatch.setattr(db,"_atomic_write",broken)
    stopped=db.stop_session(run=root,operation_id="stop",expected_state_version=1)
    assert stopped["ok"]
    assert db.read_state(run=root)["result"]["integrity"]["audit"]=="pending"
    monkeypatch.setattr(db,"_atomic_write",original)
    assert db.stop_session(run=root,operation_id="stop",expected_state_version=999)==stopped
    assert db.read_state(run=root)["result"]["integrity"]["audit"]=="ok"


def test_config_freeze_detects_corruption(tmp_path):
    root=tmp_path/"run"
    init(root,pop_size=8,n_pop=3,request_timeout=75)
    config=json.loads((root/"config_frozen.json").read_text())
    assert config["eoh"]["search"]["pop_size"]==8
    assert config["eoh"]["request_timeout"]==75
    (root/"config_frozen.json").write_text("{}")
    with pytest.raises(db.SessionError,match="config_hash_mismatch"): db.read_state(run=root)


def test_preeffect_launch_failure_can_be_collected_and_retried(tmp_path,monkeypatch):
    root=tmp_path/"run"
    init(root)
    file=tmp_path/"plan.json"
    file.write_text(json.dumps(plan(root)))
    actions.submit_plan(run=root,operation_id="plan",expected_state_version=1,file=file)
    def broken(*a,**kw): raise OSError("cannot spawn")
    monkeypatch.setattr(actions.subprocess,"Popen",broken)
    first=actions.execute(run=root,operation_id="execute",expected_state_version=2)
    state=db.read_state(run=root)
    assert state["task"]["state"]=="EXITED"
    collected=actions.collect(run=root,operation_id="collect",expected_state_version=state["state_version"])
    assert collected["state"]=="READY_TO_EXECUTE"
    second=actions.execute(run=root,operation_id="retry",expected_state_version=collected["state_version"])
    assert first["result"]["task_id"]!=second["result"]["task_id"]


def test_live_collect_does_not_consume_operation_and_stop_reconciles(tmp_path,monkeypatch):
    from agent_skill_loop.session_supervisor import mark_terminal
    root=tmp_path/"run"
    init(root)
    file=tmp_path/"plan.json"
    file.write_text(json.dumps(plan(root)))
    actions.submit_plan(run=root,operation_id="plan",expected_state_version=1,file=file)
    monkeypatch.setattr(actions.subprocess,"Popen",lambda *a,**kw: None)
    launched=actions.execute(run=root,operation_id="execute",expected_state_version=2)
    pending=actions.collect(run=root,operation_id="collect",expected_state_version=3)
    assert not pending["result"]["collected"] and pending["state_version"]==3
    stopped=db.stop_session(run=root,operation_id="stop",expected_state_version=3)
    assert stopped["run_state"]=="STOPPING"
    mark_terminal(root,launched["result"]["task_id"],"CANCELLED",0)
    state=db.read_state(run=root)
    done=actions.collect(run=root,operation_id="collect",expected_state_version=state["state_version"])
    assert done["run_state"]=="STOPPED"


@pytest.mark.parametrize("kind,expected",[("insight","failed"),("solution","rejected")])
def test_memory_failure_or_solution_rejection_keeps_evaluation(tmp_path,monkeypatch,kind,expected):
    root=tmp_path/"run"
    initialized=init(root,memory_store=str(tmp_path/"memory"))
    facts={"evidence_refs":["evaluation:fixture"],"candidates":[],"baseline":None}
    ref="rounds/round_0001/evaluation_facts.json"
    sha=actions.save(root,ref,facts)
    con=db._connect(root/"session.sqlite3")
    con.execute("UPDATE rounds SET state='WAITING_FOR_EVALUATION',evaluation_facts_ref=?,evaluation_facts_sha256=?,incumbent_after_ref='fixture-accepted',incumbent_after_objective=7 WHERE run_id=?",(ref,sha,initialized["run_id"]))
    con.close()
    def broken(*a,**kw): raise OSError("fixture storage failure")
    monkeypatch.setattr(MemoryAPI,"write",broken)
    file=tmp_path/"evaluation.json"
    file.write_text(json.dumps(dict(plan_alignment="unknown",observations=[dict(claim="fixture evidence",evidence_refs=["evaluation:fixture"])],hypotheses=[],next_search_advice={},
        memory_action=dict(kind=kind,name="test",description="fixture",project="cvrp_construct",scene="select_next_node",body="**Why:** fixture\n**How to apply:** fixture\n**Reusable Experience:** fixture"))))
    evaluated=actions.submit_evaluation(run=root,operation_id="evaluate",expected_state_version=1,file=file)
    assert evaluated["result"]["evaluation_accepted"]
    assert evaluated["result"]["memory"]["status"]==expected
    assert db.read_state(run=root)["incumbent"]["objective"]==7
    assert actions.submit_evaluation(run=root,operation_id="evaluate",expected_state_version=0,file=file)==evaluated
