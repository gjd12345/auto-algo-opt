"""Verify installed provenance and RECORD before labelling a run official."""
import base64
import hashlib
import importlib.metadata
import importlib.util
import json
import sys
from pathlib import Path
from agent_skill_loop.contracts import EOH_COMMIT


def verify_upstream() -> dict:
    dist = importlib.metadata.distribution("eoh")
    source = json.loads(dist.read_text("direct_url.json") or "{}")
    if source.get("vcs_info", {}).get("commit_id") != EOH_COMMIT or source.get("url", "").rstrip("/").removesuffix(".git") != "https://github.com/FeiLiu36/EoH":
        raise ValueError("upstream_provenance_mismatch")
    checked = 0
    for entry in dist.files or []:
        if str(entry).startswith("eoh/") and str(entry).endswith(".py"):
            if entry.hash is None or entry.hash.mode != "sha256":
                raise ValueError("upstream_record_missing")
            digest = base64.urlsafe_b64encode(hashlib.sha256(entry.locate().read_bytes()).digest()).decode().rstrip("=")
            if digest != entry.hash.value:
                raise ValueError("upstream_source_modified")
            checked += 1
    if not checked:
        raise ValueError("upstream_record_missing")
    return {"commit": EOH_COMMIT, "verified_python_files": checked, "source": source["url"]}


def adapter_source_hash() -> str:
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for package in ("agent_skill_loop", "eoh_frozen"):
        for path in sorted((root / package).rglob("*.py")):
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def loaded_identity(problem: str | None = None) -> dict:
    """Describe the code and policy resources actually loaded by this process."""
    from agent_skill_loop import session_runtime as runtime
    from agent_skill_loop.evaluator import evaluator_source_hash
    from agent_skill_loop.problems.base import get_problem
    import agent_skill_loop
    import eoh

    resource_root = Path(runtime.__file__).resolve().parents[1] / "skills" / "algorithm-optimization"
    skill_module = None
    if importlib.util.find_spec("algorithm_optimization_skill") is not None:
        import algorithm_optimization_skill as skill_module
        resource_root = Path(skill_module.__file__).resolve().parent
    elif not (resource_root / "SKILL.md").is_file():
        raise ValueError("optimization_skill_resources_missing")

    spec = get_problem(problem) if problem else None

    def location(module) -> str | None:
        value = getattr(module, "__file__", None)
        return str(Path(value).resolve()) if value else None

    try:
        distribution = importlib.metadata.distribution("agent-skill-loop")
        release_version = distribution.version
        installed_from = json.loads(distribution.read_text("direct_url.json") or "{}")
        actual_module = Path(agent_skill_loop.__file__).resolve()
        recorded_module = Path(distribution.locate_file("agent_skill_loop/__init__.py")).resolve()
        installation = ("editable" if installed_from.get("dir_info", {}).get("editable") is True else
                        "installed_distribution" if actual_module == recorded_module else "source_checkout")
    except importlib.metadata.PackageNotFoundError:
        release_version = None
        installation = "source_checkout"

    return {
        "schema_version": "algorithm-optimization-loaded-identity/v1",
        "python": {"executable": str(Path(sys.executable).resolve()), "version": sys.version.split()[0]},
        "installation": {"mode": installation, "distribution_version": release_version,
                         "wheel_sha256": None, "wheel_hash_reason": "wheel_bytes_not_available_in_loaded_process"},
        "modules": {
            "agent_skill_loop": location(agent_skill_loop),
            "algorithm_optimization_skill": location(skill_module),
            "optimization_skill_resource_root": str(resource_root.resolve()),
            "eoh": location(eoh),
        },
        "runtime_source_sha256": runtime._runtime_source_hash(),
        "optimization_skill_sha256": runtime._skill_content_hash(),
        "evaluator_sha256": evaluator_source_hash(),
        "adapter_source_sha256": adapter_source_hash(),
        "upstream": verify_upstream(),
        "problem": {
            "problem_id": spec.problem_id,
            "problem_spec_hash": spec.content_hash,
        } if spec is not None else None,
    }
