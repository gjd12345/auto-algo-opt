"""Verify installed provenance and RECORD before labelling a run official."""
import base64
import hashlib
import importlib.metadata
import json
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
