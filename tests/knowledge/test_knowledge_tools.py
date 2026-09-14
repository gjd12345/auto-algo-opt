from __future__ import annotations

import json
from pathlib import Path

from knowledge_tools.core import (
    GENERIC_RUN_INDEX,
    _framework_signal,
    _is_headline_summary,
    _is_run_candidate,
    _substantive_evidence_refs,
    _workspace_whitelist,
    classify_path,
    parse_run_container,
    search_release,
)
from knowledge_tools.dashboard import _evidence_flags, tokenize_query


def test_framework_memory_is_not_a_problem_heuristic() -> None:
    result = classify_path("eoh_rag/memory.py", "tsp construct memory for travelling salesman")
    assert result["framework_signal"] is True
    assert result["category"] == "optimization_frameworks_experiments"


def test_official_obp_example_is_implementation_not_framework() -> None:
    result = classify_path("official_eoh/examples/bp_online/prob.py", "online bin packing priority")
    assert result["framework_signal"] is False
    assert result["problem_family"] == "online_bin_packing"
    assert result["category"] == "implementation"


def test_routing_alias_does_not_make_cvrp() -> None:
    result = classify_path("docs/ISOLATION.md", "process isolation notes")
    assert result["problem_family"] != "cvrp"


def test_bp_script_maps_to_online_bin_packing() -> None:
    result = classify_path("scripts/analyze_bp_scale_proxy.py")
    assert result["problem_family"] == "online_bin_packing"
    assert result["category"] == "implementation"


def test_solomon_instance_is_cvrp_data() -> None:
    result = classify_path("go_solver/solomon_benchmark_d25/rc101.json")
    assert result["problem_family"] == "cvrp"
    assert result["role"] == "data"
    assert result["category"] == "supporting_evidence"


def test_chinese_result_dir_is_run_candidate() -> None:
    path = "agent_records/archive/obsidian_20260718/自主科研循环_2026-07-13_235608/结果/example.json"
    assert _is_run_candidate(path, "unknown") is True


def test_605_summary_is_clue_not_independent() -> None:
    path = "agent_records/archive/obsidian_20260718/自主科研循环_2026-07-13_235608/结果/阶段A-605精英代码结构相似度_2026-07-14_000239.json"
    assert _is_headline_summary(path) is True
    parsed = parse_run_container(path, b'{"status": "ok"}', {"problem_family": "unknown"})
    assert parsed["independence"] == "summary_clue"


def test_run_index_inventory_is_not_substantive_or_evaluation() -> None:
    assert _substantive_evidence_refs([GENERIC_RUN_INDEX, "gap:x"]) == ["gap:x"]
    flags = _evidence_flags({"evidence_refs": [GENERIC_RUN_INDEX], "code_refs": [], "attributes": {}})
    assert flags["eval"] is False


def test_code_evidence_ref_counts_as_located_code() -> None:
    flags = _evidence_flags({
        "evidence_refs": ["code:eoh_rag_workspace/problems/bin_packing_online/bin_packing_solver.go"],
        "code_refs": [],
        "attributes": {},
    })
    assert flags["code"] is True


def test_plan_startup_pins_resolved_release_directory() -> None:
    text = Path("knowledge_workspace/plan_startup.md").read_text(encoding="utf-8")
    assert "Path.resolve()" in text
    assert "manifest.release_id" in text
    assert "does not match directory" in text
    assert "(Resolve-Path $pointer).Path" not in text


def test_dashboard_tokenize_matches_backend_2opt() -> None:
    terms = tokenize_query("TSP 2-opt")
    assert "2opt" in terms
    assert "tsp" in terms
    assert "2" not in terms


def test_search_ranks_method_above_problem(tmp_path: Path) -> None:
    release = tmp_path / "rel"
    release.mkdir()
    (release / "index.json").write_text(
        json.dumps({
            "release_id": "test",
            "entries": [
                {
                    "id": "problem-cvrp",
                    "title": "Capacitated vehicle routing (CVRP)",
                    "type": "problem",
                    "category": "problem",
                    "problem_family": "cvrp",
                    "tags": ["cvrp"],
                    "summary": "CVRP granular tabu neighbourhood is out of scope here",
                    "search_text": "CVRP granular tabu",
                    "content_sha256": "a" * 64,
                },
                {
                    "id": "method-cvrp-granular-tabu",
                    "title": "Granular tabu search",
                    "type": "method",
                    "category": "method",
                    "problem_family": "cvrp",
                    "tags": ["cvrp", "granular", "tabu"],
                    "summary": "CVRP granular tabu",
                    "search_text": "CVRP granular tabu",
                    "content_sha256": "b" * 64,
                },
            ],
        }),
        encoding="utf-8",
    )
    (release / "manifest.json").write_text("{}", encoding="utf-8")
    result = search_release(release, "CVRP granular tabu", 2)
    assert result["results"][0]["id"] == "method-cvrp-granular-tabu"
    assert result["results"][0]["score"] > result["results"][1]["score"]


def test_publish_whitelist_excludes_host_records(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "inventory.json").write_text("{}", encoding="utf-8")
    (workspace / "knowledge_context.json").write_text("{}", encoding="utf-8")
    (workspace / "acceptance_report.md").write_text("note\n", encoding="utf-8")
    names = {path.name for path in _workspace_whitelist(workspace)}
    assert "inventory.json" in names
    assert "knowledge_context.json" not in names
    assert "acceptance_report.md" not in names
    assert "literature_queue" not in names


def test_framework_signal_excludes_problem_solvers() -> None:
    assert _framework_signal("eoh_rag_workspace/problems/bin_packing_online/bin_packing_solver.go") is False
    assert _framework_signal("eoh_rag/experiments/rag_context_builder.py") is True


def _search_fixture(tmp_path: Path, entries: list[dict]) -> dict:
    release = tmp_path / "rel"
    release.mkdir()
    (release / "index.json").write_text(
        json.dumps({"release_id": "test", "entries": entries}),
        encoding="utf-8",
    )
    (release / "manifest.json").write_text("{}", encoding="utf-8")
    return {"release": release, "entries": entries}


def test_search_title_beats_body_only(tmp_path: Path) -> None:
    fixture = _search_fixture(tmp_path, [
        {
            "id": "a",
            "title": "Granular neighbourhood search",
            "type": "method",
            "category": "method",
            "problem_family": "unknown",
            "tags": ["granular"],
            "summary": "",
            "search_text": "unrelated body",
            "content_sha256": "a" * 64,
        },
        {
            "id": "b",
            "title": "Unrelated title",
            "type": "method",
            "category": "method",
            "problem_family": "unknown",
            "tags": [],
            "summary": "",
            "search_text": "granular appears only in the body",
            "content_sha256": "b" * 64,
        },
    ])
    result = search_release(fixture["release"], "granular", 2)
    assert result["results"][0]["id"] == "a"
    assert result["results"][0]["score"] > result["results"][1]["score"]


def test_search_attributes_interface_hit(tmp_path: Path) -> None:
    fixture = _search_fixture(tmp_path, [
        {
            "id": "impl-select-next",
            "title": "Route construction",
            "type": "implementation",
            "category": "implementation",
            "problem_family": "cvrp",
            "tags": [],
            "summary": "",
            "search_text": "no mention of the interface here",
            "attributes": {"interface": "select_next_node(route, ...)"},
            "content_sha256": "a" * 64,
        },
    ])
    result = search_release(fixture["release"], "select_next_node", 2)
    assert result["results"][0]["id"] == "impl-select-next"


def test_search_drops_single_ascii_char(tmp_path: Path) -> None:
    fixture = _search_fixture(tmp_path, [
        {
            "id": "tabu-entry",
            "title": "Tabu search",
            "type": "method",
            "category": "method",
            "problem_family": "unknown",
            "tags": ["tabu"],
            "summary": "",
            "search_text": "tabu",
            "content_sha256": "a" * 64,
        },
    ])
    result = search_release(fixture["release"], "a tabu", 2)
    assert result["results"][0]["id"] == "tabu-entry"
    # Full coverage over the single surviving term "tabu", not 1/2 terms.
    assert result["results"][0]["score"] == 4.6875


def test_search_family_alias_expansion(tmp_path: Path) -> None:
    fixture = _search_fixture(tmp_path, [
        {
            "id": "cvrp-entry",
            "title": "Route optimisation",
            "type": "method",
            "category": "method",
            "problem_family": "cvrp",
            "tags": [],
            "summary": "",
            "search_text": "unrelated body text",
            "content_sha256": "a" * 64,
        },
    ])
    result = search_release(fixture["release"], "vehicle routing", 2)
    assert result["results"][0]["id"] == "cvrp-entry"


def test_search_chinese_family_alias(tmp_path: Path) -> None:
    fixture = _search_fixture(tmp_path, [
        {
            "id": "obp-entry",
            "title": "Residual score",
            "type": "method",
            "category": "method",
            "problem_family": "online_bin_packing",
            "tags": [],
            "summary": "",
            "search_text": "unrelated english body",
            "content_sha256": "a" * 64,
        },
    ])
    result = search_release(fixture["release"], "装箱", 2)
    assert result["results"][0]["id"] == "obp-entry"


def test_search_chinese_construct_alias(tmp_path: Path) -> None:
    fixture = _search_fixture(tmp_path, [
        {
            "id": "nn-construct",
            "title": "Nearest neighbor construct",
            "type": "method",
            "category": "method",
            "problem_family": "tsp",
            "tags": ["construct"],
            "summary": "",
            "search_text": "english only",
            "content_sha256": "a" * 64,
        },
    ])
    result = search_release(fixture["release"], "CVRP savings 构造", 2)
    assert any(item["id"] == "nn-construct" for item in result["results"])


def test_search_2opt_normalization(tmp_path: Path) -> None:
    fixture = _search_fixture(tmp_path, [
        {
            "id": "neighbor-2opt",
            "title": "Neighbor 2-opt repair",
            "type": "method",
            "category": "method",
            "problem_family": "unknown",
            "tags": ["2-opt"],
            "summary": "",
            "search_text": "2-opt repair",
            "content_sha256": "a" * 64,
        },
    ])
    result = search_release(fixture["release"], "2opt", 2)
    assert result["results"][0]["id"] == "neighbor-2opt"
