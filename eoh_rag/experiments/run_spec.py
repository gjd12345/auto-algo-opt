"""将实验清单展开为稳定、可审计的单次运行契约。"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class RunSpec:
    suite: str
    problem: str
    arm: str
    generation: int
    repeat: int
    seed: int
    run_key: str
    output_dir: Path

def validate_run_manifest(manifest: dict[str, Any]) -> list[str]:
    """校验 seed 与隔离策略，并一次返回全部错误。"""
    errors: list[str] = []
    seeds = manifest.get("seed_list")
    if seeds is not None:
        if not isinstance(seeds, list) or not all(isinstance(seed, int) for seed in seeds):
            errors.append("seed_list must be a list of integers")
        elif manifest.get("repeats", 1) != len(seeds):
            errors.append("repeats must equal len(seed_list)")
    if manifest.get("outcome_policy") == "disabled":
        for index, arm in enumerate(manifest.get("arms", [])):
            if (arm.get("rag") or {}).get("outcome_file"):
                errors.append(f"arm[{index}] outcome_file forbidden by outcome_policy=disabled")
    if manifest.get("prev_run_chain") is False:
        for index, arm in enumerate(manifest.get("arms", [])):
            if (arm.get("rag") or {}).get("use_prev_run_dir_chain"):
                errors.append(f"arm[{index}] prev-run chain forbidden")
    return errors

def expand_run_specs(manifest: dict[str, Any], output_root: Path) -> list[RunSpec]:
    """按 seed→problem→arm→generation 展开，保证配对实验相邻。"""
    errors = validate_run_manifest(manifest)
    if errors:
        raise ValueError("; ".join(errors))
    repeats = int(manifest.get("repeats", 1))
    seeds = manifest.get("seed_list") or list(range(repeats))
    specs: list[RunSpec] = []
    generations = manifest.get("generations", [0])
    for repeat, seed in enumerate(seeds, start=1):
        for problem in manifest.get("problems", []):
            arms = [arm for arm in manifest.get("arms", []) if not arm.get("problems") or problem in arm["problems"]]
            for arm in arms:
                for generation in generations:
                    run_key = f"{manifest['suite']}/{problem}/{arm['name']}/{seed}"
                    out = output_root / run_key
                    if len(generations) > 1:
                        out /= f"g{generation}"
                    specs.append(RunSpec(str(manifest["suite"]), str(problem), str(arm["name"]), int(generation), repeat, int(seed), run_key, out))
    unique_keys = [(spec.run_key, spec.generation) for spec in specs]
    if len(unique_keys) != len(set(unique_keys)):
        raise ValueError("expanded run keys must be unique")
    return specs
