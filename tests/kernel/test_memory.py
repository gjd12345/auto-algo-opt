from __future__ import annotations

import pytest
import json
from pathlib import Path

from agent_skill_loop.memory import MemoryAPI, MemoryEntry


def _insight(name="tie-break"):
    return MemoryEntry(
        name=name,
        description="CVRP 平局排序的经验",
        type="insight",
        project="cvrp_construct",
        scene="select_next_node",
        body="平局时保留容量约束。\n\n**Why:** fixture 评测显示错误减少。\n\n**How to apply:** 只在同一接口合同内参考。",
    )


def test_memory_writes_indexes_reads_and_rejects_conflict(tmp_path):
    api = MemoryAPI(tmp_path / "memory_store")
    written = api.write(_insight())
    assert written["written"] is True
    result = api.read("平局排序", project="cvrp_construct", scene="select_next_node", limit=4)
    assert result["memories"][0]["reference"] == "cvrp_construct/insight_tie-break@v0001"
    loaded = api.read_version(result["memories"][0]["reference"])
    assert loaded["name"] == "tie-break"
    with pytest.raises(ValueError, match="version_conflict"):
        api.write(_insight())


def test_memory_rejects_sensitive_values_and_bad_solution_shape(tmp_path):
    api = MemoryAPI(tmp_path / "memory_store")
    with pytest.raises(ValueError, match="sensitive"):
        api.write(MemoryEntry(**{**_insight().__dict__, "body": "token: abc\n\n**Why:** fixture.\n\n**How to apply:** never."}))
    with pytest.raises(ValueError, match="reusable"):
        api.write(MemoryEntry(**{**_insight("solution").__dict__, "type": "solution"}))


def test_memory_persists_provenance_and_detects_published_version_tampering(tmp_path):
    api = MemoryAPI(tmp_path / "memory")
    written = api.write(_insight("integrity"), provenance={"evidence_ref": "evaluation:fixture"})
    loaded = api.read_version(written["reference"])
    assert loaded["provenance"] == {"evidence_ref": "evaluation:fixture"}
    path = tmp_path / "memory" / "cvrp_construct" / "insight_integrity__v0001.md"
    path.write_text(path.read_text(encoding="utf-8").replace("fixture 评测", "changed 评测"), encoding="utf-8")
    with pytest.raises(ValueError, match="hash_mismatch"):
        api.read_version(written["reference"])


def test_corrupt_entry_is_isolated_and_missing_current_sidecar_is_rejected(tmp_path):
    api = MemoryAPI(tmp_path / "memory")
    local = api.write(_insight("local"))
    broken = api.write(MemoryEntry(
        "broken", "other project", "insight", "other_problem", "select_next_node",
        "bounded\n\n**Why:** fixture\n\n**How to apply:** test",
    ))
    broken_path = tmp_path / "memory" / "other_problem" / "insight_broken__v0001.md"
    broken_path.write_text(broken_path.read_text(encoding="utf-8").replace("bounded", "changed"), encoding="utf-8")
    result = api.read("平局排序", project="cvrp_construct", scene="select_next_node")
    assert [item["reference"] for item in result["memories"]] == [local["reference"]]
    assert result["degraded"] is True and result["diagnostics"][0]["error_code"] == "memory_body_hash_mismatch"
    assert api.write(_insight("still-writable"))["written"] is True

    current_path = tmp_path / "memory" / "cvrp_construct" / "insight_local__v0001.md"
    current_path.with_suffix(".json").unlink()
    with pytest.raises(ValueError, match="metadata_missing"):
        api.read_version(local["reference"])


def test_unversioned_legacy_solution_remains_readable(tmp_path):
    from agent_skill_loop.memory.api import _render
    api = MemoryAPI(tmp_path / "memory")
    entry = MemoryEntry("legacy", "old solution", "solution", "cvrp_construct", "select_next_node",
                        "**Reusable Experience:** historical format")
    path = tmp_path / "memory" / "cvrp_construct" / "solution_legacy.md"
    path.parent.mkdir(parents=True)
    path.write_text(_render(entry), encoding="utf-8")
    loaded = api.read_version("cvrp_construct/solution_legacy@v0001")
    assert loaded["format_status"] == "legacy_compatible"
    assert loaded["integrity"] == "legacy_unverified"


@pytest.mark.parametrize("corruption", ["array", "null", "version_array"])
def test_malformed_sidecar_does_not_block_other_operations(tmp_path, corruption):
    api = MemoryAPI(tmp_path / "memory")
    broken = api.write(_insight("broken"))
    sidecar = Path(broken["path"]).with_suffix(".json")
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    replacement = [] if corruption == "array" else None
    if corruption == "version_array":
        replacement = {**metadata, "format_version": []}
    sidecar.write_text(json.dumps(replacement), encoding="utf-8")
    result = api.write(_insight("healthy"), operation_key="run:publish")
    assert result["written"] and result["index_updated"]
    assert api.write(_insight("healthy"), operation_key="run:publish")["replayed"]
    search = api.read("", project="cvrp_construct")
    assert search["degraded"]
    assert [item["reference"] for item in search["memories"]] == [result["reference"]]
    with pytest.raises(ValueError, match="memory_(metadata|format_version)_invalid"):
        api.read_version(broken["reference"])


@pytest.mark.parametrize("field", ["content_sha256", "body_sha256", "schema", "format_version"])
def test_current_sidecar_requires_complete_contract(tmp_path, field):
    api = MemoryAPI(tmp_path / "memory")
    result = api.write(_insight())
    sidecar = Path(result["path"]).with_suffix(".json")
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    del metadata[field]
    sidecar.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="memory_.*_invalid"):
        api.read_version(result["reference"])


@pytest.mark.parametrize("damage", ["body", "missing_body"])
def test_damaged_latest_revision_does_not_resurrect_old_advice(tmp_path, damage):
    api = MemoryAPI(tmp_path / "memory")
    first = api.write(_insight("revised"))
    second = api.write(_insight("revised"), based_on=first["reference"])
    path = Path(second["path"])
    if damage == "body":
        path.write_text("corrupt", encoding="utf-8")
    else:
        path.unlink()
    result = api.read("", project="cvrp_construct")
    assert result["degraded"] and result["memories"] == []
    assert "insight_revised" not in api.reindex().read_text(encoding="utf-8")
    assert api.read_version(first["reference"])["version"] == 1
    with pytest.raises(ValueError, match="memory_based_on_not_latest"):
        api.write(_insight("revised"), based_on=first["reference"])


def test_memory_read_uses_stable_entrypoint_scene(tmp_path):
    api = MemoryAPI(tmp_path / "memory_store")
    api.write(MemoryEntry(
        name="free-scene-label",
        description="场景标签不应影响接口检索",
        type="insight",
        project="cvrp_construct",
        scene="select_next_node",
        body="原始标签写入正文。\n\n**Why:** fixture。\n\n**How to apply:** 继续按接口检索。",
    ))
    result = api.read("cvrp_construct select_next_node", project="cvrp_construct", scene="select_next_node")
    assert result["memories"][0]["reference"].endswith("@v0001")


def test_memory_update_and_cross_project_scope_are_versioned(tmp_path):
    api = MemoryAPI(tmp_path / "memory")
    base = MemoryEntry(
        "same", "same problem insight", "insight", "cvrp_construct", "select_next_node",
        "one\n\n**Why:** first\n\n**How to apply:** use one",
    )
    other = MemoryEntry(
        "other", "other problem insight", "insight", "other_problem", "select_next_node",
        "other\n\n**Why:** other\n\n**How to apply:** use other",
    )
    first = api.write(base)
    second = api.write(
        MemoryEntry(**{**base.__dict__, "body": "two\n\n**Why:** second\n\n**How to apply:** use two"}),
        based_on=first["reference"],
    )
    api.write(other)
    assert first["reference"].endswith("@v0001")
    assert second["reference"].endswith("@v0002")
    assert api.read_version(second["reference"])["body"].startswith("two")
    assert [row["reference"] for row in api.read("insight", project="cvrp_construct", scene="select_next_node")["memories"]] == [second["reference"]]
    assert not api.read("other", project="cvrp_construct", scene="select_next_node")["memories"]
