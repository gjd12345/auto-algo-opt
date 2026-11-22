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


def test_search_exact_id_and_unknown_id_lookup(tmp_path: Path) -> None:
    fixture = _search_fixture(tmp_path, [
        {
            "id": "method-lit-cvrp-local-granular-tabu-search",
            "title": "Granular Tabu Search",
            "type": "method",
            "category": "method",
            "problem_family": "cvrp",
            "tags": ["cvrp", "granular", "tabu"],
            "summary": "Toth and Vigo GTS.",
            "search_text": "granular tabu",
            "content_sha256": "a" * 64,
        },
    ])
    hit = search_release(fixture["release"], "method-lit-cvrp-local-granular-tabu-search", 5)
    assert hit["exact_id_lookup"] is True
    assert hit["exact_id_found"] is True
    assert [r["id"] for r in hit["results"]] == ["method-lit-cvrp-local-granular-tabu-search"]

    miss = search_release(fixture["release"], "method-cvrp-granular-tabu", 5)
    assert miss["exact_id_lookup"] is True
    assert miss["exact_id_found"] is False
    assert miss["total"] == 0
    assert miss["results"] == []


def test_search_family_context_weak_match_and_filters(tmp_path: Path) -> None:
    fixture = _search_fixture(tmp_path, [
        {
            "id": "method-lit-cvrp-construct-clarke-wright-savings-merge",
            "title": "Clarke-Wright savings merge",
            "type": "method",
            "category": "method",
            "problem_family": "cvrp",
            "tags": ["cvrp", "literature"],
            "summary": "Original savings procedure: merge singleton depot routes by ranked savings.",
            "search_text": "Parallel Clarke-Wright savings merge.",
            "attributes": {"eoh_map": {"status": "not_mappable", "adapter_kind": "not_mappable"}},
            "content_sha256": "a" * 64,
        },
        {
            "id": "method-cvrp-savings-next-node",
            "title": "Savings formula used as a next-node score",
            "type": "method",
            "category": "method",
            "problem_family": "cvrp",
            "tags": ["cvrp", "savings", "construct"],
            "summary": "Greedy next-node savings score.",
            "search_text": "The formula is Clarke-Wright savings, not full merge.",
            "attributes": {"interface": "select_next_node", "eoh_map": {"status": "possible"}},
            "content_sha256": "b" * 64,
        },
    ])
    cw = search_release(fixture["release"], "Clarke–Wright 并行合并", 5)
    assert cw["results"][0]["id"] == "method-lit-cvrp-construct-clarke-wright-savings-merge"

    weak = search_release(fixture["release"], "CVRP 量子退火不存在方法", 5)
    assert weak["total"] == 0
    assert weak["results"] == []
    assert weak["weak_match_only"] is True

    filtered = search_release(
        fixture["release"],
        "节约量",
        5,
        problem_family="CVRP",
        entry_type="method",
        interface="select_next_node",
    )
    assert [r["id"] for r in filtered["results"]] == ["method-cvrp-savings-next-node"]

    # Negative mention in body/not_the_original must NOT satisfy --interface filter
    neg_dir = tmp_path / "neg"
    neg_dir.mkdir()
    cw_only_body = _search_fixture(neg_dir, [
        {
            "id": "method-lit-cw",
            "title": "Clarke-Wright savings merge",
            "type": "method",
            "category": "method",
            "problem_family": "cvrp",
            "tags": ["cvrp", "savings"],
            "summary": "Not select_next_node.",
            "search_text": "Full CW merge is not select_next_node.",
            "attributes": {
                "not_the_original": "Full CW merge is not select_next_node.",
                "eoh_map": {"status": "not_mappable", "adapter_kind": "not_mappable"},
            },
            "content_sha256": "c" * 64,
        },
    ])
    neg_res = search_release(cw_only_body["release"], "节约量", 5, interface="select_next_node")
    assert neg_res["total"] == 0


def test_repo_workspace_and_published_releases_audit_contracts() -> None:
    import hashlib
    import subprocess
    from knowledge_tools.core import read_entry, validate_release, validate_workspace

    repo = Path(__file__).resolve().parents[2]
    ws = validate_workspace(repo / "knowledge_workspace")
    assert ws["ok"] is True, ws["errors"][:10]

    v0 = validate_release(repo / "knowledge_store/releases/20260914-main-d6433549-kb-v0")
    assert v0["ok"] is True, v0["errors"][:10]

    v1 = validate_release(repo / "knowledge_store/releases/20261121-main-audit-kb-v1")
    assert v1["ok"] is True, v1["errors"][:10]

    cur = validate_release(repo / "knowledge_store/current")
    assert cur["ok"] is True, cur["errors"][:10]

    # Exact lookup of H-003, R5, and fixed granular-tabu ID
    for eid in (
        "method-lit-cvrp-local-granular-tabu-search",
        "evidence-cvrp-depot-start-phase-h003",
        "method-cvrp-s2-r5-spiral",
    ):
        item = read_entry(repo / "knowledge_store/current", eid)
        assert item["id"] == eid

    cw = search_release(repo / "knowledge_store/current", "Clarke–Wright 并行合并", 3)
    assert cw["results"][0]["id"] == "method-lit-cvrp-construct-clarke-wright-savings-merge"

    unknown_id = search_release(repo / "knowledge_store/current", "evidence-unknown-study-999", 3)
    assert unknown_id["total"] == 0
    assert unknown_id["results"] == []

    # Verify all 7 CVRP historical implementation code_refs resolve at pinned commit d6433549
    verified = 0
    for meta_path in sorted((repo / "knowledge_workspace/entries").glob("impl-cvrp-*.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        for ref in meta.get("code_refs", []):
            blob = subprocess.check_output(
                ["git", "-C", str(repo), "show", f"d6433549dea055aa3a6ef460686198b3d1888234:{ref['path']}"]
            )
            assert hashlib.sha256(blob).hexdigest() == ref["sha256"]
            verified += 1
    assert verified == 7

    # Verify all commit-pinned attributes.artifact_refs resolve cleanly in git and match SHA-256
    def _walk_refs(obj):
        if isinstance(obj, dict):
            if obj.get("commit") and obj.get("path"):
                yield obj
            for v in obj.values():
                yield from _walk_refs(v)
        elif isinstance(obj, list):
            for it in obj:
                yield from _walk_refs(it)

    pinned_verified = 0
    for meta_path in sorted((repo / "knowledge_workspace/entries").glob("*.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        for ref in _walk_refs(meta.get("attributes") or {}):
            spec = f"{ref['commit']}:{ref['path']}"
            blob = subprocess.check_output(["git", "-C", str(repo), "show", spec])
            lf_sha = hashlib.sha256(blob.replace(b"\r\n", b"\n")).hexdigest()
            assert lf_sha == ref["sha256"], f"{meta_path.name}: {spec} sha mismatch"
            pinned_verified += 1
    assert pinned_verified >= 18


def test_cli_search_without_query_supports_structural_filters(capsys: pytest.CaptureFixture[str]) -> None:
    from knowledge_tools.cli import main

    repo = Path(__file__).resolve().parents[2]
    rc = main([
        "search",
        "--release", str(repo / "knowledge_store/current"),
        "--paradigm", "local_search",
        "--tier", "verified_experiment",
        "--variant", "standard_cvrp",
        "--comparison-mode", "local_recomputed",
        "--limit", "20",
    ])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["filter_only"] is True
    assert out["total"] >= 1
    assert any(hit["id"] == "method-cvrp-intra-2opt" for hit in out["results"])
