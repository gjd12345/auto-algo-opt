from __future__ import annotations

import pytest

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
