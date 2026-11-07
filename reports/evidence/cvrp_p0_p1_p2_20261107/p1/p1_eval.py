
import gzip, hashlib, json, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import numpy as np
sys.path.insert(0,str(Path.cwd()))
from agent_skill_loop.evaluator import SubprocessEvaluator, _validate_candidate_ast, evaluator_source_hash
from agent_skill_loop.problems.cvrp import build_suite, suite_hash
from agent_skill_loop.problems.base import get_problem

root=Path(sys.argv[1])/"p1"
root.mkdir()
def save(name,x):
    (root/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
c6=Path("reports/evidence/cvrp_super_agent_trials_20261107/C/best_code.py").read_text(encoding="utf-8")
assert sha(c6)=="141d99b6f7c62e60313feb2c520889a957da9ae00fd5138798f4de3c30e25627"
gate="    if mask.sum() >= 2 and current_node != depot:"
mid=c6.index(gate)
end=c6.index("    # Fallback: pure incumbent scoring",mid)
select="""            if mask[idx]:
                val = corrected[idx]
            else:
                val = base[idx] - 1e-6 * dem[idx]
"""
assert c6.count(select)==1
versions={
    "V0":c6[:mid]+c6[end:],
    "V1":c6,
    "V2":c6.replace(select,"            if not mask[idx]:\n                continue\n            val = corrected[idx]\n"),
    "V3":c6.replace(" * mask.astype(float)","").replace(select,"            val = corrected[idx]\n"),
}
defs={
    "V0":"Base score plus original tiny demand tie break; no capacity penalty",
    "V1":"Original C6; penalize mask members and rank all feasible candidates",
    "V2":"Same penalty and trigger; strictly rank only mask members when triggered",
    "V3":"Same trigger and penalty formula; apply to all feasible candidates and rank all",
}
protocol={"evaluator_sha256":evaluator_source_hash(),"cohorts":{"50":40,"100":40,"200":40},
          "data_seed":"64-bit SHA256 prefix of cvrp-p1-mechanism-v1/<size>/<index>","versions":{v:{"sha256":sha(c),"definition":defs[v]} for v,c in versions.items()},
          "fixed":"0.60 radial weight, 0.01 penalty coefficient, original demand tie break, band and activation trigger",
          "tracing":"Wrap the exact evaluator decision callback and replay every fixture with identical frozen code; verify all distances equal the evaluator results",
          "primary":"Paired mean distance difference versus V0; paired percentile bootstrap (20,000 draws, seed 2026110711)"}
for v,code in versions.items():
    (root/f"{v}.py").write_bytes(code.encode("utf-8"))
save("protocol_frozen.json",protocol)
spec=get_problem("cvrp_construct")
suites={}
for n in (50,100,200):
    rows=[]
    for i in range(40):
        seed=int(sha(f"cvrp-p1-mechanism-v1/{n}/{i}")[:16],16)
        inst=build_suite(seed,split="heldout",count=1,size=n)["instances"][0]
        inst["instance_id"]=f"mechanism-{n}-{i:02}"
        rows.append(inst)
    suites[n]={"problem":spec.problem_id,"split":"heldout","instances":rows,"content_hash":suite_hash(spec.problem_id,"heldout",rows)}
    save(f"suite_{n}.json",suites[n])

def measure(key):
    n,v=key
    result=SubprocessEvaluator(120).evaluate(versions[v],suites[n],collect_partial=True)
    if not result.valid:
        raise ValueError((n,v,result.error_code,result.error_detail))
    save(f"evaluation_{n}_{v}.json",result.as_dict())
    env={"np":np,"__builtins__":dict(spec.safe_builtins)}
    exec(compile(_validate_candidate_ast(versions[v],spec),"<candidate>","exec"),env)
    fn=env[spec.entrypoint]
    totals={"steps":0,"eligible_gate":0,"applied_gate":0,"outside_mask_on_gate":0,"different_from_base_at_same_state":0}
    with gzip.open(root/f"trace_{n}_{v}.jsonl.gz","wt",encoding="utf-8") as trace:
        for inst,obj in zip(suites[n]["instances"],result.instance_objectives,strict=True):
            steps=0
            def observed(current,depot,nodes,capacity,demands,matrix):
                nonlocal steps
                steps+=1
                chosen=int(fn(current,depot,nodes,capacity,demands,matrix))
                d=matrix[current][nodes]
                q=demands[nodes]
                base=d-0.6*matrix[depot][nodes]
                lo=float(np.min(base))
                band=1e-3*(float(np.max(base)-lo)+1.0)
                mask=base<=lo+band
                eligible=bool(mask.sum()>=2 and current!=depot)
                applied=eligible and v!="V0"
                idx=int(np.where(nodes==chosen)[0][0])
                base_winner=int(nodes[np.argmin(base-1e-6*q)])
                penalty=0.01*abs(capacity-q[idx])/max(float(d[idx]),1e-9) if applied and (v=="V3" or mask[idx]) else 0.0
                totals["steps"]+=1
                totals["eligible_gate"]+=eligible
                totals["applied_gate"]+=applied
                totals["outside_mask_on_gate"]+=applied and not mask[idx]
                totals["different_from_base_at_same_state"]+=chosen!=base_winner
                row={"instance":inst["instance_id"],"step":steps,"current":current,"remaining_capacity":capacity,"selected":chosen,
                     "inside_mask":bool(mask[idx]),"mask_size":int(mask.sum()),"gate":applied,"base_winner":base_winner,
                     "base_score":float(base[idx]),"penalty":float(penalty),"corrected_score":float(base[idx]+penalty-1e-6*q[idx])}
                trace.write(json.dumps(row,ensure_ascii=True)+"\n")
                return chosen
            replay,_=spec.evaluate_instances(observed,[inst])
            if replay[0]!=obj:
                raise ValueError((n,v,inst["instance_id"],replay,obj))
    print(f"{n}/{v} {result.objective:.6f} {totals}",flush=True)
    return key,np.asarray(result.instance_objectives),totals

rng=np.random.default_rng(2026110711)
with ThreadPoolExecutor(max_workers=3) as ex:
    scored={k:(x,t) for k,x,t in ex.map(measure,[(n,v) for n in suites for v in versions])}
summary={}
for n in suites:
    idx=rng.integers(0,40,size=(20000,40))
    def diff(a,b):
        d=scored[n,a][0]-scored[n,b][0]
        return {"mean_distance_delta":float(d.mean()),"ci95":[float(z) for z in np.percentile(d[idx].mean(axis=1),[2.5,97.5])],
                "win_tie_loss":[int(np.sum(d<-1e-9)),int(np.sum(abs(d)<=1e-9)),int(np.sum(d>1e-9))]}
    summary[n]={v:{"mean":float(scored[n,v][0].mean()),"vs_V0":diff(v,"V0"),"trace":scored[n,v][1]} for v in versions}
    summary[n]["V2_minus_V1"]=diff("V2","V1")
save("summary.json",summary)
print(json.dumps(summary,ensure_ascii=True))
