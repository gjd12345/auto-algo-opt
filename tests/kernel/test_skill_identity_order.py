"""The release identity must order resource names identically on Windows/Linux."""
import hashlib
from pathlib import Path
from agent_skill_loop.session_runtime import _skill_content_hash


def test_skill_identity_uses_case_sensitive_posix_resource_names():
    root=Path(__file__).resolve().parents[2]/"skills/algorithm-optimization"
    resources={p.relative_to(root).as_posix(): p.read_bytes()
               for p in root.rglob("*") if p.is_file() and p.suffix in {".md", ".yaml"}}
    sha=hashlib.sha256()
    for name in sorted(resources):
        sha.update(("skills/algorithm-optimization/"+name).encode())
        sha.update(resources[name])
    assert _skill_content_hash()==sha.hexdigest()
