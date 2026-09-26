"""Restore exposed island_605 BP training data and calibrate without model calls."""
from __future__ import annotations

import argparse
import ast
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = {"data": args.source / "official_eoh/examples/bp_online/get_instance.py",
             "evaluator": args.source / "official_eoh/examples/bp_online/prob.py",
             "historical_best": args.source / "evidence/final_batch_20260630/best_codes/bp_online_best.py"}
    texts = {key: path.read_text(encoding="utf-8") for key, path in paths.items()}
    tree = ast.parse(texts["data"])
    init = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "__init__")
    assignment = next(n for n in init.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Subscript))
    dataset = ast.literal_eval(assignment.value)
    assert len(dataset) == 5
    instances = []
    for name, value in dataset.items():
        items = value["items"]
        assert len(items) == value["num_items"] == 5000
        assert all(type(x) is int and 0 < x <= 100 for x in items)
        instances.append({"instance_id": name, "capacity": 100, "items": items,
                          "reference_objective": int(np.ceil(np.sum(items) / 100)),
                          "reference_kind": "analytical_reference"})
    mean_l1 = float(np.mean([x["reference_objective"] for x in instances]))
    for instance in instances:
        instance["dataset_mean_l1"] = mean_l1
    provenance = {"classification": "historically_exposed_training_only",
        "restoration": "archived_data_and_BPONLINE_semantics_not_full_commit_reproduction",
        "reported_historical_commit": "e1b90b337d3b6e97e359e03915ab8eedc5f33a8a",
        "historical_commit_available_locally": False,
        "source_files": {key: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for key, path in paths.items()},
        "capacity_override": 100, "dataset": "Weibull 5k", "instances": instances}
    from agent_skill_loop.problems import bp_island605 as restored
    write(restored.ASSET, provenance)
    args.output.mkdir(parents=True, exist_ok=True)
    for key, path in paths.items():
        (args.output / (key + ".source.py")).write_bytes(path.read_bytes())
    write(args.output / "restoration.json", {k: v for k, v in provenance.items() if k != "instances"})

    # Execute only the inspected original BPONLINE class, without imports,
    # superclass or constructor: Broad/heldout initialization is never used.
    source_tree = ast.parse(texts["evaluator"])
    cls = next(n for n in source_tree.body if isinstance(n, ast.ClassDef) and n.name == "BPONLINE")
    cls.bases = []
    cls.body = [n for n in cls.body if not isinstance(n, ast.FunctionDef) or n.name != "__init__"]
    scope = {"np": np}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), str(paths["evaluator"]), "exec"), scope)
    original = scope["BPONLINE"]()
    original.instances = {"Weibull 5k": {x["instance_id"]: {"capacity": 100, "num_items": 5000, "items": x["items"]} for x in instances}}
    original.lb = {"Weibull 5k": mean_l1}

    from agent_skill_loop.evaluator import SubprocessEvaluator, evaluator_source_hash
    suite = restored.build_suite()
    write(args.output / "train_suite.json", suite)
    results = []
    for name, code in [("best_fit", restored.BASELINE_CODE), ("historical_B1", texts["historical_best"])]:
        context = {"np": np}
        exec(compile(code, name, "exec"), context)
        old_objective = original.evaluate_program(code, context["score"])
        result = SubprocessEvaluator(timeout=60).evaluate(code, suite)
        row = {"name": name, "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
               "original_objective": old_objective, "restored": asdict(result)}
        results.append(row)
        write(args.output / "calibration.json", {"rows": results, "evaluator_hash": evaluator_source_hash(), "solver_calls": len(results) * 2, "provider_requests": 0})
        assert result.valid, result.error_code
        assert abs(result.objective - old_objective) < 1e-12
        print(name, "original=", old_objective, "restored=", result.objective,
              "bins=", result.metrics["bins_used"], flush=True)
    assert results[0]["restored"]["objective"] > 0, "baseline saturated; do not start search"
    assert abs(results[1]["restored"]["objective"] - 0.006741) < 0.000001, "historical B1 reproduction mismatch"


if __name__ == "__main__":
    main()
