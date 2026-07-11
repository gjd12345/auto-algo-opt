"""导入并冻结 Core held-out 实例，不覆盖 hash 不一致的既有文件。"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
from pathlib import Path

TSP_CORE = ["eil51", "st70", "kroA100", "ch130", "kroA200", "tsp225", "a280", "pcb442", "rat575", "rat783", "pr1002", "pcb3038"]
CVRP_CORE = ["X-n101-k25", "X-n129-k18", "X-n153-k22", "X-n200-k36", "X-n251-k28", "X-n303-k21", "X-n351-k40", "X-n401-k29", "X-n502-k39", "X-n1001-k43"]

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def import_file(source: Path, target: Path) -> str:
    """先校验最小格式，再原子替换；既有文件内容冲突时停止。"""
    text = source.read_text(encoding="utf-8", errors="replace")
    if "NODE_COORD_SECTION" not in text or "EOF" not in text:
        raise ValueError(f"invalid benchmark format: {source}")
    source_hash = sha256(source)
    if target.exists():
        if sha256(target) != source_hash:
            raise ValueError(f"refusing to overwrite hash mismatch: {target}")
        return source_hash
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    shutil.copyfile(source, temporary)
    temporary.replace(target)
    return source_hash

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("eoh_rag_workspace/held_out/core"))
    parser.add_argument("--registry", type=Path, default=Path("eoh_rag_workspace/experiments/manifests/core_benchmark_registry.json"))
    args = parser.parse_args()
    records = []
    for problem, names, suffix in (("tsp_construct", TSP_CORE, ".tsp"), ("cvrp_construct", CVRP_CORE, ".vrp")):
        for name in names:
            source = args.source_dir / f"{name}{suffix}"
            target = args.output_dir / problem / source.name
            records.append({"problem": problem, "instance": name, "path": target.as_posix(), "sha256": import_file(source, target)})
    args.registry.parent.mkdir(parents=True, exist_ok=True)
    args.registry.write_text(json.dumps({"schema_version": "core-benchmarks/v1", "instances": records}, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
