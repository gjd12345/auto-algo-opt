"""Pure evidence projection, no model or physics calls."""

import json
from collections import Counter
from pathlib import Path

from .store import config, connect, read, record
from .ledger import counts


def build(run):
    with connect(run) as db:
        root, conf = record(db), config(db)
        rows = []
        cumulative = 0
        for row in db.execute("SELECT * FROM rounds ORDER BY id"):
            plan = read(run, json.loads(row["plan"])) if row["plan"] else None
            facts = read(run, json.loads(row["facts"])) if row["facts"] else None
            effects = [dict(e) for e in db.execute("SELECT * FROM effects WHERE round=?", (row["id"],))]
            requests = sum(e["kind"] == "MODEL_REQUEST" and e["state"] not in ("RESERVED", "CANCELLED_NOT_STARTED") for e in effects)
            cumulative += requests
            online = sum(e["kind"] == "ONLINE_PROFILE" and e["state"] not in ("RESERVED", "CANCELLED_NOT_STARTED") for e in effects)
            candidates = facts["candidates"] if facts else []
            qualities = [str(c.get("ranking_key") or c.get("error", "unknown")) for c in candidates]
            incumbent_key = None
            if facts and facts["incumbent_after"]:
                from optics_backend.offline import reload_facts
                incumbent_key = reload_facts(Path(run) / facts["incumbent_after"]["directory"], conf["task_contract_hash"])["ranking_key"]
            memory_refs = plan["memory_basis"] if plan else []
            from .runtime import memory_status
            rows.append({"round": row["id"], "plan": plan["hypothesis"] if plan else None,
                         "requests_delta": requests, "requests_cumulative": cumulative, "online_profiles": online,
                         "candidates": qualities, "incumbent": facts["incumbent_after"] if facts else None,
                         "incumbent_key": incumbent_key, "memory": memory_refs,
                         "memory_publication": memory_status(db, run, row["id"]),
                         "feasible_generated": sum(c.get("online_feasible") is True for c in candidates),
                         "evaluation_reused": sum("evaluation_reused_from" in c for c in candidates),
                         "duplicate_parent_count": sum(c.get("prescription_delta", {}).get("duplicate_parent") is True for c in candidates),
                         "delta_diagnostics_available": sum("prescription_delta" in c for c in candidates),
                         "valid_generated": sum("ranking_key" in c and c["ranking_key"] is not None for c in candidates),
                         "generated": len(candidates), "state": row["state"]})
        effects = [dict(e) for e in db.execute("SELECT * FROM effects")]
        external = [json.loads(e["detail"]) for e in effects if e["kind"] == "MODEL_REQUEST" and json.loads(e["detail"]).get("external_request")]
        final = read(run, json.loads(root["final"])) if root["final"] else None
        from .parent_import import accepted_receipt, parent_path
        baseline_path = str(Path(conf["bundle"]) / "assets/initial_prescription.json")
        usage = Counter()
        for item in db.execute("SELECT a.artifact FROM effects e JOIN assessments a ON a.id=e.assessment WHERE e.kind='ONLINE_PROFILE' AND e.state!='CANCELLED_NOT_STARTED'"):
            role = "baseline" if item[0] == baseline_path else "inherited_parent" if Path(item[0]).resolve() == parent_path(run) else "generated"
            usage[role] += 1
        summary = {"run_state": root["state"], "reason": root["reason"], "counts": counts(db), "rounds": rows,
                   "effect_states": dict(Counter(e["kind"] + ":" + e["state"] for e in effects)),
                   "online_profile_roles": dict(usage), "online_parent": accepted_receipt(db),
                   "external_requests": len(external), "input_tokens": sum(e.get("input_tokens") or 0 for e in external) if all(e.get("input_tokens") is not None for e in external) else None,
                   "output_tokens": sum(e.get("output_tokens") or 0 for e in external) if all(e.get("output_tokens") is not None for e in external) else None,
                   "has_unknown_effects": any(e["state"] == "UNKNOWN" for e in effects), "final": final,
                   "controller_contract_hash": conf["controller_contract_hash"], "experiment_protocol_mode": conf["experiment_protocol_mode"]}
    lines = ["# Optical Session progress", "", "Native optical prescription search, not EoH. Completed means this batch ended, not optimality. Requests/tokens cover the generation provider only; outer Agent costs are not included. Local audit is not independent verification.", "", "Counts are charged budget units; effect_states separates completed, unknown and cancelled effects. Comparable/generated does not imply online feasibility. Duplicate counts cover only candidates with delta diagnostics; older missing diagnostics remain unknown.", "", "| Round | Plan | Req Δ/Σ | Online profiles | Comparable/generated | Feasible | Parent duplicates/checked | Candidate S1 / error | Incumbent | Memory read / publication | State |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        plan = (r["plan"] or "—").replace("|", "/").replace("\n", " ")
        values = "; ".join(r["candidates"]).replace("|", "/").replace("\n", " ")
        lines.append(f"| {r['round']} | {plan} | {r['requests_delta']}/{r['requests_cumulative']} | {r['online_profiles']} | {r['valid_generated']}/{r['generated']} | {r['feasible_generated']} | {r['duplicate_parent_count']}/{r['delta_diagnostics_available']} | {values} | {r['incumbent_key']} | {r['memory'] or '—'} / {r['memory_publication']['status']} | {r['state']} |")
    lines += ["", "```json", json.dumps(summary, ensure_ascii=False, indent=2), "```", ""]
    return summary, "\n".join(lines)
