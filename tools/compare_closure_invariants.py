"""Compare semantic closure facts, excluding run-local evidence identities."""
import argparse
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def derive(root):
    config = read(root / "session/config_frozen.json")
    def population(number):
        return [{"code_sha256": x["code_sha256"], "objective": x["objective"]}
                for x in read(root / f"session/rounds/round_{number:04d}/population_snapshot.json")["members"]]
    selections = {}
    for kind in ("incumbent_top1", "archive_topk", "final_population_set"):
        inputs = read(root / f"{kind}.inputs.json")
        semantic = {"kind": kind, "metric_spec_hash": config["benchmark"]["metric_spec_hash"],
                    "members": [{"code_sha256": x["code_sha256"], "objective": x["objective"]}
                                for x in inputs["selection"]["members"]]}
        selections[kind] = {"semantic_selection_sha256": hashlib.sha256(
            json.dumps(semantic, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "selection": semantic,
            "heldout": [{"code_sha256": x["code_sha256"], "instance_objectives": x["instance_objectives"]}
                        for x in inputs["test_result"]["member_results"]]}
    seeds = read(root / "session/rounds/round_0002/seed_selection.json")
    return {"schema": "closure-semantic-invariants/v1", "benchmark": config["benchmark"],
            "runtime_hash": config["runtime"]["source_sha256"],
            "skill_hash": config["optimization_skill"]["content_sha256"],
            "eoh_commit": config["eoh"]["commit"], "round1_population": population(1),
            "round2_seeds": [x["code_sha256"] for x in seeds["selected_members"]],
            "round2_population": population(2), "selections": selections}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    paths = [p for root in args.paths for p in (root.rglob("closure_invariants.json") if root.is_dir() else [root])]
    if len(paths) != 2:
        raise SystemExit("exactly_two_platform_invariants_required")
    if read(paths[0]) != read(paths[1]):
        raise SystemExit("cross_platform_semantic_mismatch")
    print("cross_platform_semantic_parity: passed")
