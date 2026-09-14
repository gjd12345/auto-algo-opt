from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from knowledge_tools import CLASSIFICATION_VERSION, SCHEMA_VERSION
from knowledge_tools.core import (
    _atomic_pointer,
    _required_sections,
    _safe_rel,
    build_release,
    parse_run_container,
    read_entry,
    resolve_release,
    sha256_file,
    validate_release,
    validate_workspace,
)


def _minimal_workspace(tmp_path: Path, *, crlf: bool = False) -> tuple[Path, Path]:
    workspace = tmp_path / "ws"
    entries = workspace / "entries"
    entries.mkdir(parents=True)
    (workspace / "inventory.json").write_text(
        json.dumps({
            "schema_version": SCHEMA_VERSION,
            "classification_rule_version": CLASSIFICATION_VERSION,
            "tracked_file_count": 0,
            "files": [],
            "coverage": {"inventory_complete": True, "classification_coverage": 1.0},
        }),
        encoding="utf-8",
    )
    (workspace / "sources.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    sections = _required_sections("")
    markdown = "\n\n".join(f"{section}\n\nBody text for {section}." for section in sections) + "\n"
    if crlf:
        markdown = markdown.replace("\n", "\r\n")
    md_path = entries / "m-test.md"
    md_path.write_text(markdown, encoding="utf-8", newline="")
    (entries / "m-test.json").write_text(
        json.dumps({
            "id": "m-test",
            "type": "method",
            "category": "method",
            "title": "Test method",
            "problem_family": "unknown",
            "source_refs": [],
            "evidence_refs": ["gap:x"],
            "code_refs": [],
            "status": "reviewed",
            "content_sha256": sha256_file(md_path),
        }),
        encoding="utf-8",
    )
    return workspace, md_path


def test_build_validate_read_roundtrip(tmp_path: Path) -> None:
    workspace, md_path = _minimal_workspace(tmp_path)
    store = tmp_path / "store"
    built = build_release(workspace, store)
    assert built["entry_count"] == 1
    validation = validate_release(store)
    assert validation["ok"] is True, validation["errors"]
    entry = read_entry(store, "m-test")
    assert entry["id"] == "m-test"
    assert entry["body"] == md_path.read_text(encoding="utf-8")
    assert "## 定义或方法步骤" in entry["body"]


def test_read_entry_crlf(tmp_path: Path) -> None:
    workspace, md_path = _minimal_workspace(tmp_path, crlf=True)
    raw = md_path.read_bytes()
    assert b"\r\n" in raw
    store = tmp_path / "store"
    build_release(workspace, store)
    entry = read_entry(store, "m-test")
    assert entry["id"] == "m-test"
    assert entry["body"] == md_path.read_text(encoding="utf-8")


def test_orphan_md_flagged(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    entries = workspace / "entries"
    entries.mkdir(parents=True)
    (workspace / "inventory.json").write_text(
        json.dumps({
            "schema_version": SCHEMA_VERSION,
            "classification_rule_version": CLASSIFICATION_VERSION,
            "tracked_file_count": 0,
            "files": [],
            "coverage": {"inventory_complete": True, "classification_coverage": 1.0},
        }),
        encoding="utf-8",
    )
    (workspace / "sources.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    (entries / "orphan.md").write_text("## 定义或方法步骤\n", encoding="utf-8")
    result = validate_workspace(workspace)
    assert any("orphan" in error for error in result["errors"])


def test_safe_rel_rejects_traversal() -> None:
    for path in ("..\\evil", "C:/evil", "a/../b", "/abs"):
        with pytest.raises(ValueError):
            _safe_rel(path)


def test_atomic_pointer_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*args: object, **kwargs: object) -> None:
        raise OSError("symlink not permitted")

    monkeypatch.setattr("knowledge_tools.core.os.symlink", _raise)
    store = tmp_path / "store"
    release_dir = store / "releases" / "rel1"
    release_dir.mkdir(parents=True)
    (release_dir / "manifest.json").write_text("{}", encoding="utf-8")
    (release_dir / "index.json").write_text("{}", encoding="utf-8")
    mode = _atomic_pointer(store, release_dir)
    assert mode == "path_file"
    pointer = store / "current.path"
    assert pointer.exists()
    assert "releases/rel1" in pointer.read_text(encoding="utf-8")
    assert not (store / "current").exists()
    assert not os.path.lexists(store / "current")
    assert resolve_release(store) == release_dir.resolve()
    assert resolve_release(store / "current") == release_dir.resolve()


def test_yaml_typeerror_is_corrupt_not_crash() -> None:
    pytest.importorskip("yaml")
    result = parse_run_container("runs/x.yaml", b"as_of: 2020-01-01\n", {"problem_family": "unknown"})
    assert result["status"] == "corrupt"


def test_validated_requires_locatable_evaluation_and_real_relations(tmp_path: Path) -> None:
    workspace, _ = _minimal_workspace(tmp_path)
    meta_path = workspace / "entries" / "m-test.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["status"] = "validated"
    meta["evidence_refs"] = ["evaluation:missing-report-without-suite-metric-budget"]
    meta["relations"] = {"problems": ["problem-does-not-exist"]}
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    result = validate_workspace(workspace)
    assert result["ok"] is False
    joined = " ".join(result["errors"])
    assert "missing entry" in joined
    assert "locatable evaluation" in joined


def test_version_diff_tracks_metadata(tmp_path: Path) -> None:
    from knowledge_tools.core import _version_diff
    previous = tmp_path / "old"
    previous.mkdir()
    (previous / "index.json").write_text(json.dumps({
        "release_id": "old",
        "entries": [{
            "id": "m-test",
            "content_sha256": "a" * 64,
            "metadata_sha256": "b" * 64,
        }],
    }), encoding="utf-8")
    entries = [{
        "id": "m-test",
        "content_sha256": "a" * 64,
        "metadata_sha256": "c" * 64,
        "status": "unread",
    }]
    diff = _version_diff(previous, entries)
    assert "m-test" in diff["changed"]
    assert "m-test" in diff["changed_metadata"]
    assert diff["changed_body"] == []
