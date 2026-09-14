"""Positive Session repair/solution paths with real deterministic evaluations."""
import ast
import json
import sqlite3
import time

import pytest
pytest.importorskip("eoh")

from agent_skill_loop import session_runtime as db, session_actions as actions
from agent_skill_loop.memory.api import MemoryAPI, MemoryEntry
from agent_skill_loop.skill_store import load_skill
from eoh_frozen.smoke import fixture_provider


# Fixed development-suite regression, based on the locally archived candidate.
# Scores are recomputed through the real solver, never supplied by the fixture.
CAPACITY_CODE = '''def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return 0
    dists = distance_matrix[current_node][unvisited_nodes]
    dem = demands[unvisited_nodes]
    avg_demand = demands.sum() / max(1, len(demands) - 1)
    fit = np.abs(rest_capacity - dem - avg_demand) / max(avg_demand, 1.0)
    scores = dists + 0.5 * fit * fit * np.minimum(dists, distance_matrix[depot][unvisited_nodes])
    return int(unvisited_nodes[np.argmin(scores)])
'''


@pytest.mark.parametrize("repair_mode",["off","bounded"])
def test_session_publishes_verified_solution_with_optional_repair(tmp_path,monkeypatch,repair_mode):
    monkeypatch.setenv("SESSION_POSITIVE_KEY","fixture")
    def responder(prompt,index):
        if prompt=="1+1=?": return 200,"2"
        tree=ast.parse(CAPACITY_CODE)
        tree.body[0].body.insert(0,ast.parse(f"variant = {index}").body[0])
        code=ast.unparse(tree)
        if '"role":"execute_repair"' in prompt:
            return 200,json.dumps(dict(algorithm="capacity ranking",code=code,repair_summary="Replace forbidden ix_ with allowed argmin."))
        if repair_mode=="bounded": code=code.replace("np.argmin","np.ix_")
        return 200,"{capacity ranking}\n```python\n"+code+"\n```"

    root=tmp_path/"run"
    memory_api=MemoryAPI(tmp_path/"memory")
    previous=memory_api.write(MemoryEntry(
        name="capacity-fixture", description="earlier bounded capacity solution",
        type="solution", project="cvrp_construct", scene="select_next_node",
        body="## Execution\nEarlier fixture.\n**Why:** Earlier evidence.\n**How to apply:** Reevaluate.\n**Reusable Experience:** Keep the interface fixed.",
    ))
    with fixture_provider("cvrp_construct",responder=responder) as (endpoint,prompts):
        db.initialize_session(output=root,operation_id="init",eoh_model="fixture",eoh_endpoint=endpoint,
            eoh_api_key_env="SESSION_POSITIVE_KEY",eoh_max_requests=16,eoh_round_max_requests=16,
                search_policy_defaults={"pop_size":2,"n_pop":1,"max_sample_nums":1},seed=20260908,count=3,size=20,round_wall_seconds=60,
            repair_mode=repair_mode,repair_max_requests=4 if repair_mode=="bounded" else 0,
            memory_store=str(tmp_path/"memory"),solution_threshold=.01)
        file=tmp_path/"plan.json"
        file.write_text(json.dumps(dict(round_id=1,direction="capacity fit scoring",operations=[dict(type="replace",target="ranking",mechanism="capacity fit")],
            preserve="interface",hypothesis="unproven",feedback_basis=None,memory_basis=[])))
        planned=actions.submit_plan(run=root,operation_id="plan",expected_state_version=1,file=file)
        actions.execute(run=root,operation_id="execute",expected_state_version=planned["state_version"])
        until=time.monotonic()+75
        while time.monotonic()<until:
            state=db.read_state(run=root)
            if state["task"]["state"]=="EXITED": break
            time.sleep(.1)
        else: pytest.fail("supervisor did not settle")
        collected=actions.collect(run=root,operation_id="collect",expected_state_version=state["state_version"])
        facts=actions.read_evaluation(run=root)["result"]
        skill=load_skill(root/facts["best_generated_ref"])
        assert skill.mean_objective < facts["baseline"]["objective"]*.99
        candidate=next(x for x in facts["candidates"] if x["code_sha256"]==skill.code_sha256 and x["valid"])
        assert (root/candidate["generation_request_ref"]).is_file()
        if repair_mode=="bounded":
            repaired=[x for x in facts["candidates"] if x["revision"]=="repair_1" and x["valid"]]
            assert repaired
            for item in repaired:
                original=next(x for x in facts["candidates"] if x["candidate_id"]==item["candidate_id"] and x["revision"]=="original")
                assert not original["valid"]
                assert original["code_sha256"]!=item["code_sha256"]
                assert original["evaluation_id"]!=item["evaluation_id"]
                assert (root/item["repair_request_ref"]).is_file()
                assert (root/item["generation_request_ref"]).is_file()
        file=tmp_path/"evaluation.json"
        evidence=f"evaluation:{candidate['evaluation_id']}"
        file.write_text(json.dumps(dict(plan_alignment="aligned",observations=[dict(claim="Improves this frozen development suite by over 1 percent.",evidence_refs=[evidence])],
            hypotheses=[],next_search_advice={},memory_action=dict(kind="solution",name="capacity-fixture",description="capacity fit on frozen fixture suite",
            project="cvrp_construct",scene="select_next_node",source_skill_ref=facts["best_generated_ref"],memory_based_on=previous["reference"],evidence_ref=evidence,
            body=f"## Execution\nAsset: {facts['best_generated_ref']}\n**Why:** {evidence}; fixed development suite only.\n**How to apply:** Reevaluate on new data.\n**Reusable Experience:** Capacity fit scaling; no generalization claim."))))
        result=actions.submit_evaluation(run=root,operation_id="evaluate",expected_state_version=collected["state_version"],file=file)
        assert result["result"]["memory"]["status"]=="published"
        published=MemoryAPI(tmp_path/"memory").read_version(result["result"]["memory"]["reference"])
        assert published["type"]=="solution" and published["version"]==2
        assert published["provenance"]["source_skill_ref"]==facts["best_generated_ref"]
        assert actions.submit_evaluation(run=root,operation_id="evaluate",expected_state_version=0,file=file)==result
        assert actions.finish_round(run=root,operation_id="finish",expected_state_version=result["state_version"],decision="complete")["run_state"]=="COMPLETED"
        with sqlite3.connect(root/"session.sqlite3") as con:
            assert con.execute("SELECT COUNT(*) FROM requests").fetchone()[0]==len(prompts)
            assert con.execute("SELECT COUNT(*) FROM requests WHERE purpose='eoh_repair'").fetchone()[0]==sum('"role":"execute_repair"' in p for p in prompts)
            assert con.execute("SELECT COUNT(*) FROM requests WHERE purpose NOT IN ('eoh_probe','eoh_generation','eoh_repair')").fetchone()[0]==0
            for item in facts["candidates"]:
                row=con.execute("SELECT candidate_id,revision,code_sha256 FROM solver_calls WHERE evaluation_id=?",(item["evaluation_id"],)).fetchone()
                assert row==(item["candidate_id"],item["revision"],item["code_sha256"])
            assert con.execute("SELECT COUNT(*) FROM memory_writes WHERE status='published'").fetchone()[0]==1
