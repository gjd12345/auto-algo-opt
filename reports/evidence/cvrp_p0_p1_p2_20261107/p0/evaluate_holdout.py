
import csv
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd()))
from agent_skill_loop.evaluator import SubprocessEvaluator, evaluator_source_hash
from agent_skill_loop.problems.cvrp import build_suite, suite_hash

root = Path(sys.argv[1])
protocol = json.loads((root / "protocol_frozen.json").read_text(encoding="utf-8"))
assert evaluator_source_hash() == protocol["evaluator_sha256"]
def sha(data):
    return hashlib.sha256(data).hexdigest()
def write_json(name, value):
    data = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    (root / name).write_bytes(data)
    return sha(data)

codes = {}
for label, item in protocol["candidate_identities"].items():
    data = (root / item["ref"]).read_bytes()
    assert sha(data) == item["sha256"]
    codes[label] = data.decode("utf-8")

sizes = [g["customers"] for g in protocol["cohorts"]]
suites, all_seeds, manifest = {}, set(), {}
dev = json.loads(Path("reports/evidence/cvrp_super_agent_reference_20261107/dev_suite.json").read_text(encoding="utf-8"))
assert dev["content_hash"] == protocol["training_suite_sha256"]
def signature(instance):
    return sha(json.dumps({k:v for k,v in instance.items() if k!="instance_id"}, sort_keys=True).encode("utf-8"))
seen = {signature(x) for x in dev["instances"]}
for group in protocol["cohorts"]:
    n, count = group["customers"], group["instances"]
    seeds, instances = [], []
    for i in range(count):
        seed = int(sha(f"cvrp-p0-holdout-v1/{n}/{i}".encode("ascii"))[:16], 16)
        assert seed not in all_seeds
        all_seeds.add(seed)
        seeds.append(seed)
        inst = build_suite(seed, split="heldout", count=1, size=n)["instances"][0]
        inst["instance_id"] = f"heldout-{n}-{i:02}"
        sig = signature(inst)
        assert sig not in seen
        seen.add(sig)
        instances.append(inst)
    suite = {"problem": protocol["problem"], "split": "heldout", "instances": instances}
    suite["content_hash"] = suite_hash(suite["problem"], suite["split"], instances)
    suites[n] = suite
    name = f"suite_{n}.json"
    manifest[n] = {"ref": name, "content_hash": suite["content_hash"], "file_sha256": write_json(name, suite), "seeds": seeds}
write_json("dataset_manifest.json", manifest)

def evaluate(task):
    n, label = task
    result = SubprocessEvaluator(timeout=120).evaluate(codes[label], suites[n], collect_partial=True)
    facts = result.as_dict()
    write_json(f"evaluation_{n}_{label}.json", facts)
    if not result.valid or len(result.instance_objectives) != len(suites[n]["instances"]):
        raise RuntimeError(f"{n}/{label} failed: {result.error_code} / {result.error_detail}")
    if result.suite_hash != suites[n]["content_hash"]:
        raise RuntimeError(f"{n}/{label} suite identity mismatch")
    print(f"Completed {n}/{label}: {result.objective:.5f}", flush=True)
    return n, label, np.array(result.instance_objectives, dtype=float)

dist = {n:{} for n in sizes}
with ThreadPoolExecutor(max_workers=3) as pool:
    for n, label, objectives in pool.map(evaluate, [(n,k) for n in sizes for k in codes]):
        dist[n][label] = objectives

rng = np.random.default_rng(protocol["bootstrap"]["seed"])
tol = protocol["paired_win_tie_loss_tolerance"]
out = {}
with (root / "instance_results.csv").open("w", encoding="utf-8", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["customers", "instance_id", "seed", *codes])
    for n in sizes:
        a = dist[n]
        for i, inst in enumerate(suites[n]["instances"]):
            writer.writerow([n, inst["instance_id"], manifest[n]["seeds"][i], *(a[label][i] for label in codes)])
        idx = rng.integers(0, len(a["NN"]), size=(protocol["bootstrap"]["samples"], len(a["NN"])))
        def compare(candidate, reference):
            c, r = a[candidate], a[reference]
            delta = r - c
            relative = 100 * delta.mean() / r.mean()
            boot = 100 * delta[idx].mean(axis=1) / r[idx].mean(axis=1)
            return {"improvement_pct": float(relative), "ci95_pct": [float(x) for x in np.percentile(boot, [2.5,97.5])],
                    "wins": int(sum(delta > tol)), "ties": int(sum(abs(delta) <= tol)), "losses": int(sum(delta < -tol))}
        out[n] = {"n": len(a["NN"]), "distances": {label: {"mean": float(v.mean()), "median": float(np.median(v))} for label,v in a.items()},
                  "vs_NN": {label: compare(label,"NN") for label in ("A","B","C")}, "C_vs_A": compare("C","A"), "C_vs_B": compare("C","B")}
write_json("summary.json", out)
print(json.dumps(out, ensure_ascii=True))
