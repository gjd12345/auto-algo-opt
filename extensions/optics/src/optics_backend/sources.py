"""Allowlisted binary import of the reviewed T1 assets, not the author archive."""

from pathlib import Path
import zipfile

from .artifacts import canonical, digest, save, strict

PACKAGE_ROOT = "AIFO_optics_physics_review_20260915/"
TASKS = {"optics-t1-singlet", "optics-t3-triplet"}
FILES = (
    "assets/ACCEPTANCE.md", "assets/acceptance_rules.json",
    "assets/task_spec.json", "assets/evaluation_protocol.json",
    "assets/initial_prescription.json", "evaluate.py",
    "physics/acceptance.py", "physics/candidate_loader.py", "physics/constraints.py",
    "physics/empirical_gate.py", "physics/evaluator.py", "physics/legacy_core.py",
)


def import_task(archive: Path, target: Path, expected_source_sha256: str, task_id="optics-t1-singlet") -> dict:
    if task_id not in TASKS:
        raise ValueError("UNREGISTERED_OPTICS_TASK")
    task_prefix = f"02_harbor_tasks/tasks/physical-sciences/physics/{task_id}/"
    source_hash = digest(archive.read_bytes())
    if source_hash != expected_source_sha256.lower():
        raise ValueError("SOURCE_PACKAGE_HASH_MISMATCH")
    if target.exists():
        raise ValueError("IMPORT_TARGET_EXISTS")
    payloads, rows = {}, []
    with zipfile.ZipFile(archive) as source:
        names = source.namelist()
        if len(names) != len(set(names)):
            raise ValueError("DUPLICATE_ZIP_ENTRY")
        sums = {}
        for line in source.read(PACKAGE_ROOT + "SHA256SUMS.txt").decode("utf-8").splitlines():
            if not line.strip():
                continue
            sha, name = line.split(None, 1)
            name = name.lstrip(" *")
            if name in sums:
                raise ValueError("DUPLICATE_CHECKSUM_ENTRY")
            sums[name] = sha
        for name in FILES:
            relative = task_prefix + "environment/" + name
            entry = source.getinfo(PACKAGE_ROOT + relative)
            if entry.file_size > 8_000_000 or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("UNSAFE_ZIP_ENTRY")
            raw = source.read(entry)
            if digest(raw) != sums.get(relative):
                raise ValueError("SOURCE_FILE_HASH_MISMATCH: " + name)
            payloads[name] = raw
            rows.append({"source_relative_path": relative, "local_relative_path": name,
                         "raw_sha256": digest(raw), "byte_length": len(raw),
                         "transformation": "none"})
    manifest = {"schema_id": "optics-task-import/v1", "task_id": task_id,
                "source_package_sha256": source_hash, "declared_task_version": "1.4.1",
                "files": rows}
    manifest["task_contract_hash"] = digest(canonical(manifest))
    target.mkdir(parents=True)
    for name, raw in payloads.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(raw)
    save(target / "import_manifest.json", manifest)
    load_task(target, manifest["task_contract_hash"])
    return manifest


def load_task(root: Path, expected_task_hash: str) -> dict:
    manifest = strict((root / "import_manifest.json").read_bytes())
    body = {k: v for k, v in manifest.items() if k != "task_contract_hash"}
    if digest(canonical(body)) != expected_task_hash or manifest["task_contract_hash"] != expected_task_hash:
        raise ValueError("TASK_MANIFEST_HASH_MISMATCH")
    if [r["local_relative_path"] for r in manifest["files"]] != list(FILES):
        raise ValueError("TASK_FILE_SET_MISMATCH")
    for row in manifest["files"]:
        path = root / row["local_relative_path"]
        if path.is_symlink() or root.resolve() not in path.resolve().parents:
            raise ValueError("UNSAFE_TASK_PATH")
        raw = path.read_bytes()
        if len(raw) != row["byte_length"] or digest(raw) != row["raw_sha256"]:
            raise ValueError("TASK_FILE_HASH_MISMATCH: " + row["local_relative_path"])
    rules = strict((root / "assets/acceptance_rules.json").read_bytes())
    task = strict((root / "assets/task_spec.json").read_bytes())
    if manifest["task_id"] not in TASKS or task["task_id"] != manifest["task_id"]:
        raise ValueError("TASK_REGISTRY_MISMATCH")
    for section, prefix in (("data_sha256", "assets"), ("implementation_sha256", "physics")):
        for name, sha in rules[section].items():
            if f"{prefix}/{name}" not in FILES or digest((root / prefix / name).read_bytes()) != sha:
                raise ValueError("ACCEPTANCE_IDENTITY_MISMATCH")
    return manifest
