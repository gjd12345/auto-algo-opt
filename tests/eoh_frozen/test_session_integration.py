import json
import sqlite3
import time

import pytest
pytest.importorskip("eoh")

from agent_skill_loop import session_runtime as db
from agent_skill_loop import session_actions as actions
from eoh_frozen.smoke import fixture_provider


def test_detached_session_two_rounds_with_memory_and_exact_ledgers(tmp_path,monkeypatch):
    monkeypatch.setenv("SESSION_FIXTURE_KEY","fixture")
    root=tmp_path/"run"
    with fixture_provider("cvrp_construct") as (endpoint,prompts):
        db.initialize_session(output=root,operation_id="init",eoh_model="fixture",eoh_endpoint=endpoint,eoh_api_key_env="SESSION_FIXTURE_KEY",
            search_policy_defaults={"pop_size":2,"n_pop":1,"max_sample_nums":1},eoh_max_requests=20,count=1,size=6,memory_store=str(tmp_path/"memory"))
        memory_ref=None
        for number in (1,2):
            state=db.read_state(run=root)
            memory=[]
            if memory_ref:
                assert actions.memory_search(run=root)["result"]["memories"]
                actions.memory_read(run=root,reference=memory_ref)
                memory=[memory_ref]
            doc=dict(round_id=number,direction="test distance ranking",operations=[dict(type="replace",target="ranking",mechanism="distance")],preserve="interface",hypothesis="unproven",memory_basis=memory,
                feedback_basis=dict(round_id=number-1,evaluation_ref=state["feedback_ref"],suite_hash=json.loads((root/"dev_suite.json").read_text())["content_hash"]) if number>1 else None)
            file=tmp_path/"plan.json"
            file.write_text(json.dumps(doc))
            planned=actions.submit_plan(run=root,operation_id=f"plan-{number}",expected_state_version=state["state_version"],file=file)
            executed=actions.execute(run=root,operation_id=f"execute-{number}",expected_state_version=planned["state_version"])
            assert actions.execute(run=root,operation_id=f"execute-{number}",expected_state_version=0)==executed
            until=time.monotonic()+60
            while time.monotonic()<until:
                state=db.read_state(run=root)
                if state["task"]["state"]=="EXITED": break
                time.sleep(.1)
            else: pytest.fail("supervisor did not finish")
            collected=actions.collect(run=root,operation_id=f"collect-{number}",expected_state_version=state["state_version"])
            assert collected["state"]=="WAITING_FOR_EVALUATION"
            facts=actions.read_evaluation(run=root)["result"]
            assert facts["incumbent_after"] is not None
            assert any(x["origin"]=="generated" for x in facts["candidates"])
            if number==2:
                assert "fixture memory body" in (root/"rounds/round_0002/round_context.txt").read_text()
                exchanges=list((root/"rounds/round_0002/eoh_run/results/exchanges").glob("*.json"))
                assert any("fixture memory body" in x.read_text() for x in exchanges)
            evaluation=dict(plan_alignment="unknown",observations=[dict(claim="candidate evaluated",evidence_refs=[facts["evidence_refs"][-1]])],hypotheses=[],next_search_advice={},
                memory_action=dict(kind="insight",name="fixture",description="test insight",project="cvrp_construct",scene="select_next_node",body="fixture memory body\n**Why:** fixture\n**How to apply:** test only") if number==1 else dict(kind="none"))
            file=tmp_path/"evaluation.json"
            file.write_text(json.dumps(evaluation))
            evaluated=actions.submit_evaluation(run=root,operation_id=f"eval-{number}",expected_state_version=collected["state_version"],file=file)
            assert actions.submit_evaluation(run=root,operation_id=f"eval-{number}",expected_state_version=0,file=file)==evaluated
            if number==1: memory_ref=evaluated["result"]["memory"]["reference"]
            finished=actions.finish_round(run=root,operation_id=f"finish-{number}",expected_state_version=evaluated["state_version"],decision="continue" if number==1 else "complete")
        assert finished["run_state"]=="COMPLETED"
    with sqlite3.connect(root/"session.sqlite3") as con:
        assert con.execute("SELECT COUNT(*) FROM requests").fetchone()[0]==len(prompts)
        assert con.execute("SELECT COUNT(*) FROM requests WHERE purpose NOT LIKE 'eoh_%'").fetchone()[0]==0
        assert con.execute("SELECT COUNT(*) FROM solver_calls WHERE state IN ('reserved','started')").fetchone()[0]==0
        assert con.execute("SELECT COUNT(*) FROM memory_writes WHERE status='published'").fetchone()[0]==1


@pytest.mark.parametrize("failure",["auth","deadline"])
def test_session_terminal_request_is_counted_and_assets_survive(tmp_path,monkeypatch,failure):
    monkeypatch.setenv("SESSION_FIXTURE_KEY","fixture")
    def responder(prompt,index):
        if failure=="deadline": time.sleep(2)
        return (401,"unauthorized") if failure=="auth" else (200,"2")
    root=tmp_path/"run"
    with fixture_provider("cvrp_construct",responder=responder) as (endpoint,prompts):
        db.initialize_session(output=root,operation_id="init",eoh_model="fixture",eoh_endpoint=endpoint,eoh_api_key_env="SESSION_FIXTURE_KEY",
            search_policy_defaults={"pop_size":2,"n_pop":1,"max_sample_nums":1},eoh_max_requests=5,count=1,size=6,request_timeout=.5,round_wall_seconds=5)
        file=tmp_path/"plan.json"
        file.write_text(json.dumps(dict(round_id=1,direction="test",operations=[dict(type="preserve",target="interface",mechanism="preserve")],preserve="interface",hypothesis="unproven",memory_basis=[],feedback_basis=None)))
        planned=actions.submit_plan(run=root,operation_id="plan",expected_state_version=1,file=file)
        actions.execute(run=root,operation_id="execute",expected_state_version=planned["state_version"])
        until=time.monotonic()+15
        while time.monotonic()<until:
            state=db.read_state(run=root)
            if state["task"]["state"]=="EXITED": break
            time.sleep(.1)
        else: pytest.fail("terminal failure did not settle")
        actions.collect(run=root,operation_id="collect",expected_state_version=state["state_version"])
        facts=actions.read_evaluation(run=root)["result"]
        assert facts["incumbent_after"]["origin"]=="baseline"
        assert len(prompts)==1
        with sqlite3.connect(root/"session.sqlite3") as con:
            assert con.execute("SELECT COUNT(*) FROM requests").fetchone()[0]==1
            request=con.execute("SELECT state,input_tokens,output_tokens FROM requests").fetchone()
            assert request==("unknown" if failure=="deadline" else "failed",None,None)
