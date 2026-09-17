"""Public P1 APIs. Not a Session, search controller, or budget gateway."""

from pathlib import Path
import os
import math
import subprocess
import sys
import uuid

from .artifacts import canonical, digest, load_artifact, read_verified, save, strict
from .ranking import compare, rank_key
from .sources import load_task


class OfflineFailure(RuntimeError):
    def __init__(self, exit_code: int, output: Path):
        super().__init__(f"OFFLINE_WORKER_FAILED:{exit_code}:{output}")
        self.exit_code = exit_code


def child_environment():
    # Explicit allowlist. In particular no keys, proxies, PYTHONPATH or site startup.
    names = ("SystemRoot", "WINDIR", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL")
    return {name: os.environ[name] for name in names if name in os.environ}


def evaluate(bundle: Path, task_hash: str, candidate: Path, output: Path,
             *, mode="online", response=False, timeout=600, session_run=None, assessment_id=None,
             parent=None, plan=None):
    load_task(bundle, task_hash)
    if mode not in ("online", "audit"):
        raise ValueError("UNKNOWN_EVALUATION_MODE")
    if output.exists():
        raise ValueError("OUTPUT_EXISTS")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("POSITIVE_TIMEOUT_REQUIRED")
    # Atomic directory claim precedes launch. A losing caller never writes there.
    output.mkdir(parents=True, exist_ok=False)
    owner = uuid.uuid4().hex
    save(output / "execution_request.json", {"owner_token": owner, "task_contract_hash": task_hash,
         "bundle": str(bundle.resolve()), "candidate": str(candidate.absolute()), "mode": mode,
         "response": response})
    command = [sys.executable, "-I", "-B", str(Path(__file__).with_name("worker.py")),
               "--bundle", str(bundle.resolve()), "--task-hash", task_hash,
               "--candidate", str(candidate.absolute()), "--output", str(output.resolve()), "--mode", mode,
               "--owner-token", owner]
    if response:
        command.append("--response")
    if session_run is not None:
        command += ["--session-run", str(Path(session_run).resolve()), "--assessment-id", assessment_id]
    if parent is not None:
        command += ["--parent", str(Path(parent).resolve()), "--plan", str(Path(plan).resolve())]
    try:
        child = subprocess.run(command, env=child_environment(), capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        # subprocess.run kills and waits for this single worker; it launches no descendants.
        output.mkdir(parents=True, exist_ok=True)
        save(output / "supervisor_terminal.json", {"status": "interrupted", "reason": "OFFLINE_TIMEOUT",
             "provider_requests": 0, "physics_outcome": "unknown", "retry": False})
        raise
    except OSError as exc:
        output.mkdir(parents=True, exist_ok=True)
        save(output / "supervisor_terminal.json", {"status": "failed", "reason": "WORKER_START_FAILED",
             "error": str(exc), "provider_requests": 0})
        raise
    with (output / "worker.stdout").open("xb") as stream:
        stream.write(child.stdout)
    with (output / "worker.stderr").open("xb") as stream:
        stream.write(child.stderr)
    if child.returncode:
        raise OfflineFailure(child.returncode if child.returncode in (2, 4, 5) else 4, output)
    return reload_facts(output, task_hash)


def reload_facts(output: Path, task_hash: str):
    terminal = strict((output / "terminal.json").read_bytes())
    if terminal["status"] != "complete":
        raise ValueError("ASSESSMENT_INCOMPLETE")
    for name, expected in terminal["evidence_sha256"].items():
        path = output / name
        if Path(name).is_absolute() or ".." in Path(name).parts or path.is_symlink() or output.resolve() not in path.resolve().parents:
            raise ValueError("EVIDENCE_PATH_ESCAPE")
        if digest(path.read_bytes()) != expected:
            raise ValueError("EVIDENCE_HASH_MISMATCH:" + name)
    facts = read_verified(output / "facts.json", terminal["facts_sha256"])
    identity = facts["evaluation_identity"]
    if identity["task_contract_hash"] != task_hash or digest(canonical(identity)) != facts["evaluation_identity_sha256"]:
        raise ValueError("EVALUATION_IDENTITY_MISMATCH")
    if strict((output / "assessment_identity.json").read_bytes()) != identity:
        raise ValueError("ASSESSMENT_IDENTITY_MISMATCH")
    if digest((output / "environment.json").read_bytes()) != identity["environment_manifest_hash"]:
        raise ValueError("ENVIRONMENT_IDENTITY_MISMATCH")
    relative = Path(facts["artifact_ref"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("ARTIFACT_PATH_ESCAPE")
    artifact = load_artifact(output / relative, task_hash)
    if artifact["canonical_artifact_sha256"] != identity["canonical_artifact_sha256"]:
        raise ValueError("EVALUATED_ARTIFACT_MISMATCH")
    original = read_verified(output / "upstream_result.json", facts["upstream_result_sha256"])
    if original["profiles"] != facts["profile_results"]:
        raise ValueError("PROFILE_FACTS_MISMATCH")
    if facts["mode"] != identity["mode"] or len(original["profiles"]) != (1 if facts["mode"] == "online" else 4):
        raise ValueError("PROFILE_MODE_OR_COUNT_MISMATCH")
    started = list((output / "profiles").glob("*.started.json"))
    completed = list((output / "profiles").glob("*.completed.json"))
    if len(started) != len(completed) or len(completed) != len(original["profiles"]) or terminal["profile_executions"] != len(completed):
        raise ValueError("PROFILE_LEDGER_MISMATCH")
    profile_ids = set()
    for path in completed:
        event = strict(path.read_bytes(), 20_000_000)
        begin = strict(path.with_name(path.name.replace(".completed", ".started")).read_bytes())
        if any(event[k] != begin[k] for k in ("effect_id", "profile_id", "profile_spec_hash", "mode")):
            raise ValueError("PROFILE_EVENT_MISMATCH")
        if event["profile_id"] in profile_ids or event["mode"] != facts["mode"] or event["result"] != original["profiles"].get(event["profile_id"]):
            raise ValueError("PROFILE_RESULT_MISMATCH")
        profile_ids.add(event["profile_id"])
    if facts["mode"] == "online" and facts["physics_status"] == "OK":
        profile = next(iter(original["profiles"].values()))
        if (profile["aggregate_metrics"]["quality_q"] != facts["quality_q"]
                or profile["judgment"]["constraint_vector"] != facts["constraints"]
                or profile["judgment"]["all_hard_constraints_passed"] != facts["online_feasible"]):
            raise ValueError("ONLINE_FACTS_MISMATCH")
    expected_key = rank_key(facts)
    if facts["ranking_key"] != (list(expected_key) if expected_key is not None else None):
        raise ValueError("RANKING_KEY_MISMATCH")
    from .ranking import RANKING_HASH
    if facts["ranking_contract_hash"] != RANKING_HASH:
        raise ValueError("RANKING_CONTRACT_MISMATCH")
    return facts


def compare_saved(previous: Path | None, candidate: Path, task_hash: str, output: Path):
    old = reload_facts(previous, task_hash) if previous else None
    new = reload_facts(candidate, task_hash)
    receipt = compare(old, new)
    save(output, receipt)
    return receipt
