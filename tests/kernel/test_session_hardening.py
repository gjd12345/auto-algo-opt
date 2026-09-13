import json
import os
from pathlib import Path
import subprocess
import sqlite3
import sys
import time

import pytest

from agent_skill_loop import session_runtime as db, session_actions as actions
from agent_skill_loop.memory.api import MemoryAPI, MemoryEntry
from agent_skill_loop.process_tree import ExecutionTree
from agent_skill_loop.session_supervisor import monitor_runner


def entry():
    return MemoryEntry("crash-test","fixture","insight","cvrp_construct","select_next_node",
                       "**Why:** fixture\n**How to apply:** test only")


def test_memory_kernel_lock_released_after_owner_killed(tmp_path):
    script="from pathlib import Path; from agent_skill_loop.memory.api import MemoryAPI; import sys\nwith MemoryAPI(Path(sys.argv[1]))._writer():\n print('locked',flush=True)\n sys.stdin.read()"
    owner=subprocess.Popen([sys.executable,"-c",script,str(tmp_path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                           creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
    try:
        assert owner.stdout.readline().strip()==b"locked"
        api=MemoryAPI(tmp_path)
        with pytest.raises(ValueError,match="memory_writer_busy"):
            api.write(entry())
        owner.kill()
        owner.wait(timeout=5)
        result=api.write(entry(),operation_key="recover")
        assert result["version"]==1
        assert api.write(entry(),operation_key="recover")["replayed"]
    finally:
        if owner.poll() is None: owner.kill()
        owner.wait(timeout=5)


def test_legacy_memory_pid_lock_is_reclaimed_only_after_death(tmp_path):
    api=MemoryAPI(tmp_path)
    lock=tmp_path/".writer.lock"
    lock.write_text(str(os.getpid()))
    with pytest.raises(ValueError,match="memory_writer_busy"): api.write(entry())
    child=subprocess.Popen([sys.executable,"-c","pass"])
    child.wait(timeout=5)
    lock.write_text(str(child.pid))
    assert api.write(entry())["written"]


@pytest.mark.parametrize("reason",["deadline","stop"])
def test_independent_monitor_kills_deadlocked_runner_and_child(tmp_path,reason):
    script="import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(90)']); print(p.pid,flush=True); time.sleep(90)"
    # Handshake holds the test runner until its Windows Job has been attached.
    script="import sys; sys.stdin.readline(); "+script
    process=subprocess.Popen([sys.executable,"-c",script],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
        start_new_session=os.name!="nt",creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
    tree=ExecutionTree(process)
    try:
        process.stdin.write(b"go\n"); process.stdin.close()
        child_pid=int(process.stdout.readline())
        started=time.monotonic()
        result=monitor_runner(process,started+(.15 if reason=="deadline" else 30),lambda: reason=="stop",tree=tree)
        assert result==("DEADLINE_EXCEEDED" if reason=="deadline" else "CANCELLED")
        assert time.monotonic()-started<5
        from agent_skill_loop.session_recovery import process_alive
        until=time.monotonic()+3
        while process_alive(child_pid) and time.monotonic()<until: time.sleep(.05)
        assert not process_alive(child_pid)
    finally:
        tree.terminate(); tree.close()


def test_runtime_mismatch_allows_state_stop_but_denies_mutations(tmp_path,monkeypatch):
    root=tmp_path/"run"
    db.initialize_session(output=root,operation_id="init",eoh_model="fixture",size=6,count=1)
    assert json.loads((root/"config_frozen.json").read_text())["schema_version"].endswith("/v1.1")
    monkeypatch.setattr(db,"_runtime_source_hash",lambda: "changed-runtime")
    state=db.read_state(run=root)
    assert state["integrity"]["runtime_identity"]=="mismatch"
    assert "submit_plan" not in state["allowed_actions"]
    file=tmp_path/"plan.json"; file.write_text("{}")
    for action,extra in [(actions.submit_plan,{"file":file}),(actions.execute,{}),(actions.collect,{}),
                         (actions.submit_evaluation,{"file":file}),(actions.finish_round,{"decision":"complete"})]:
        with pytest.raises(db.SessionError) as failure:
            action(run=root,operation_id="test",expected_state_version=1,**extra)
        assert failure.value.code=="RUNTIME_IDENTITY_MISMATCH"
    assert db.stop_session(run=root,operation_id="stop",expected_state_version=1)["run_state"]=="STOPPED"


def test_pre_search_policy_v11_session_is_readable_but_immutable(tmp_path):
    root=tmp_path/"legacy-run"
    db.initialize_session(output=root,operation_id="init",eoh_model="fixture",size=6,count=1)
    config=json.loads((root/"config_frozen.json").read_text())
    config["eoh"].pop("search_policy_defaults",None)
    config["eoh"].pop("search_policy_limits",None)
    config_text=json.dumps(config,ensure_ascii=False,indent=2)+"\n"
    (root/"config_frozen.json").write_bytes(config_text.encode("utf-8"))
    with sqlite3.connect(root/"session.sqlite3") as con:
        con.execute("ALTER TABLE runs DROP COLUMN search_policy_defaults_json")
        con.execute("ALTER TABLE runs DROP COLUMN search_policy_limits_json")
        con.execute("UPDATE runs SET config_sha256=?, runtime_source_sha256=?",(db._sha256(config_text),"legacy-runtime"))
    state=db.read_state(run=root)
    assert state["integrity"]["runtime_identity"]=="mismatch"
    assert state["search_policy"] is None
    assert "stop" in state["allowed_actions"]
    assert "submit_plan" not in state["allowed_actions"]
    plan_file=tmp_path/"legacy-plan.json"
    plan_file.write_text("{}",encoding="utf-8")
    with pytest.raises(db.SessionError) as failure:
        actions.submit_plan(run=root,operation_id="plan",expected_state_version=1,file=plan_file)
    assert failure.value.code=="RUNTIME_IDENTITY_MISMATCH"
    assert db.stop_session(run=root,operation_id="stop",expected_state_version=1)["run_state"]=="STOPPED"


def prepare_evaluation(root,tmp_path):
    db.initialize_session(output=root,operation_id="init",eoh_model="fixture",size=6,count=1,memory_store=str(tmp_path/"memory"))
    ref="rounds/round_0001/evaluation_facts.json"
    sha=actions.save(root,ref,{"evidence_refs":[],"candidates":[]})
    con=db._connect(root/"session.sqlite3")
    con.execute("UPDATE rounds SET state='WAITING_FOR_EVALUATION',evaluation_facts_ref=?,evaluation_facts_sha256=?",(ref,sha)); con.close()
    file=tmp_path/"evaluate.json"
    item=entry().as_dict(); item["kind"]=item.pop("type")
    file.write_text(json.dumps(dict(plan_alignment="unknown",observations=[],hypotheses=[],next_search_advice={},memory_action=item)))
    return file


def test_memory_publication_releases_sqlite_writer_and_preserves_concurrent_stop(tmp_path,monkeypatch):
    root=tmp_path/"run"; file=prepare_evaluation(root,tmp_path)
    original=MemoryAPI.write
    def stop_during_write(api,*args,**kw):
        state=db.read_state(run=root)
        assert state["state_version"]==3
        stopped=db.stop_session(run=root,operation_id="concurrent-stop",expected_state_version=3)
        assert stopped["run_state"]=="STOPPED"
        return original(api,*args,**kw)
    monkeypatch.setattr(MemoryAPI,"write",stop_during_write)
    result=actions.submit_evaluation(run=root,operation_id="evaluate",expected_state_version=1,file=file)
    assert result["result"]["memory"]["status"]=="published"
    assert result["run_state"]=="STOPPED" and result["state_version"]==5


def test_memory_publish_before_db_receipt_replays_one_version(tmp_path,monkeypatch):
    from agent_skill_loop import session_memory
    root=tmp_path/"run"; file=prepare_evaluation(root,tmp_path)
    original=session_memory._record_status
    def crash(con,proposal,op,status,error,reference):
        if status=="published": raise RuntimeError("receipt crash")
        return original(con,proposal,op,status,error,reference)
    monkeypatch.setattr(session_memory,"_record_status",crash)
    with pytest.raises(RuntimeError,match="receipt crash"):
        actions.submit_evaluation(run=root,operation_id="evaluate",expected_state_version=1,file=file)
    monkeypatch.setattr(session_memory,"_record_status",original)
    result=actions.submit_evaluation(run=root,operation_id="evaluate",expected_state_version=1,file=file)
    assert result["result"]["memory"]["status"]=="published"
    assert len(list((tmp_path/"memory").glob("*/*.md")))==1


def test_session_supervisor_hang_is_terminal_and_unknown_request_not_refunded(tmp_path,monkeypatch):
    from agent_skill_loop import session_supervisor
    from agent_skill_loop.session_ledger import SessionRequestBudget
    root=tmp_path/"run"
    db.initialize_session(output=root,operation_id="init",eoh_model="fixture",size=6,count=1,round_wall_seconds=.5)
    file=tmp_path/"plan.json"
    file.write_text(json.dumps(dict(round_id=1,direction="fixture",operations=[dict(type="preserve",target="interface",mechanism="preserve")],
        preserve="interface",hypothesis="unproven",feedback_basis=None,memory_basis=[])))
    actions.submit_plan(run=root,operation_id="plan",expected_state_version=1,file=file)
    con=db._connect(root/"session.sqlite3")
    run_id=db._require_run(con,action="fixture",run_id=None)["run_id"]
    con.execute("INSERT INTO tasks(task_id,run_id,round_id,state,created_at_utc) VALUES ('hung',?,1,'STARTING',?)",(run_id,db._utc_now()))
    con.execute("UPDATE rounds SET task_id='hung'")
    con.close()
    real_popen=subprocess.Popen
    def hung_runner(command,**kw):
        process=real_popen([sys.executable,"-c","import sys,time; sys.stdin.buffer.readline(); time.sleep(90)"],**kw)
        # Simulate durable reservation followed by a process hang, before a
        # provider response. No network is sent by this fault injection.
        budget=SessionRequestBudget(root,"hung")
        assert budget.reserve(purpose="eoh_probe",problem="cvrp_construct",model="fixture")
        return process
    monkeypatch.setattr(session_supervisor.subprocess,"Popen",hung_runner)
    started=time.monotonic()
    session_supervisor.run_task(root,"hung")
    assert time.monotonic()-started<5
    state=db.read_state(run=root)
    assert state["task"]["terminal_reason"]=="DEADLINE_EXCEEDED"
    assert state["task"]["state"]=="EXITED"
    collected=actions.collect(run=root,operation_id="collect",expected_state_version=state["state_version"])
    assert collected["state"]=="WAITING_FOR_EVALUATION"
    con=db._connect(root/"session.sqlite3")
    assert con.execute("SELECT state FROM requests").fetchone()[0]=="unknown"
    assert con.execute("SELECT COUNT(*) FROM task_processes").fetchone()[0]==1
    # Even a caller returning to READY_TO_EXECUTE cannot rerun this task's
    # external effects. An operation replay only returns its prior receipt.
    con.execute("UPDATE rounds SET state='READY_TO_EXECUTE'")
    con.close()
    with pytest.raises(db.SessionError,match="EFFECTFUL_TASK_ALREADY_EXISTS"):
        actions.execute(run=root,operation_id="new-execute",expected_state_version=collected["state_version"])
    assert db.read_state(run=root)["budgets"]["eoh_requests_used"]==1
