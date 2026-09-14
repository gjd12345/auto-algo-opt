from __future__ import annotations

import json
from pathlib import Path

from knowledge_tools.catalog import build_catalog, validate_catalog
from knowledge_tools.core import _workspace_whitelist, validate_workspace
from knowledge_tools.literature import (
    adapter_code,
    dump_catalog,
    harvest_catalog,
    ingest_screen,
    pack_family_batch,
    pack_screen,
    split_batch_screen,
    validate_screen,
    write_adapter_files,
)


def test_catalog_has_thirty_or_do_not_pad() -> None:
    catalog = build_catalog()
    assert validate_catalog(catalog) == []
    families = catalog["families"]
    for name in ("tsp", "cvrp", "online_bin_packing", "knapsack"):
        items = families[name]["subproblems"]
        assert len(items) == 30
        assert families[name]["fill_policy"] == "require_30"
        for item in items:
            assert 1 <= len(item["target_heuristics"]) <= 2
    for name in ("mixer_split", "insertships_routing"):
        assert families[name]["fill_policy"] == "do_not_pad"
        assert len(families[name]["subproblems"]) < 30


def test_dump_catalog_writes_json_and_markdown(tmp_path: Path) -> None:
    result = dump_catalog(tmp_path)
    assert result["ok"] is True
    payload = json.loads((tmp_path / "subproblems.json").read_text(encoding="utf-8"))
    assert payload["families"]["tsp"]["subproblems"][0]["id"] == "tsp_euclidean"
    markdown = (tmp_path / "subproblems.md").read_text(encoding="utf-8")
    assert "mixer_split" in markdown
    assert "不凑 30" in markdown


def test_harvest_is_idempotent_and_respects_existing(tmp_path: Path) -> None:
    catalog = build_catalog()
    calls = []

    def fake_search(query: str, rows: int, mailto: str | None):
        calls.append(query)
        return [{
            "openalex_id": "https://openalex.org/W1",
            "doi": "10.1000/tsp-nn",
            "title": "Nearest neighbor for Euclidean TSP",
            "authors": ["A. Author"],
            "year": 1977,
            "venue": "Journal",
            "cited_by_count": 10,
            "abstract": "A nearest neighbor tour construction is analysed.",
            "abstract_missing": False,
            "url": "https://doi.org/10.1000/tsp-nn",
        }]

    out = tmp_path / "queue"
    first = harvest_catalog(
        catalog, out, family="tsp", limit_subproblems=2,
        pause_seconds=0, search=fake_search,
    )
    second = harvest_catalog(
        catalog, out, family="tsp", limit_subproblems=2,
        pause_seconds=0, search=fake_search,
    )
    assert first["written"] == 2
    assert second["written"] == 0
    assert second["skipped_existing"] == 2
    assert len(calls) == 2
    dry = harvest_catalog(
        catalog, out, family="mixer_split", dry_run=True, pause_seconds=0, search=fake_search,
    )
    assert dry["planned"] == []
    assert dry["written"] == 0


def test_pack_screen_mentions_contract_traps(tmp_path: Path) -> None:
    queue = tmp_path / "tsp_euclidean.json"
    queue.write_text(json.dumps({
        "family": "tsp",
        "subproblem": build_catalog()["families"]["tsp"]["subproblems"][0],
        "works": [{
            "doi": "10.1000/tsp-nn",
            "year": 1977,
            "title": "NN",
            "authors": ["Rosenkrantz"],
            "abstract": "Nearest neighbor.",
        }],
    }), encoding="utf-8")
    prompt = tmp_path / "prompt.md"
    result = pack_screen(queue, prompt)
    text = prompt.read_text(encoding="utf-8")
    assert result["work_count"] == 1
    assert "Insertion into a partial tour is not select_next_node" in text
    assert "Return ONLY one JSON object" in text
    assert "Nearest Neighbor" in text


def test_validate_screen_rejects_missing_doi_and_padding() -> None:
    errors = validate_screen({
        "subproblem_id": "tsp_euclidean",
        "selected": [{"doi": "", "heuristic_name": "NN", "steps": ["go"], "eoh_map": "possible", "adapter_kind": "next_node_score"}],
        "cannot_classify": False,
    }, "tsp_euclidean")
    assert any("DOI" in item for item in errors)
    errors = validate_screen({
        "subproblem_id": "tsp_euclidean",
        "selected": [{"doi": "10.1", "heuristic_name": "NN", "steps": ["go"], "eoh_map": "possible", "adapter_kind": "next_node_score"}] * 3,
        "cannot_classify": False,
    }, "tsp_euclidean")
    assert any("longer than 2" in item for item in errors)


def test_ingest_writes_adapter_only_when_possible(tmp_path: Path) -> None:
    catalog_item = build_catalog()["families"]["tsp"]["subproblems"][0]
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps({
        "family": "tsp",
        "subproblem": catalog_item,
        "works": [{
            "doi": "10.1000/tsp-nn",
            "title": "Nearest neighbor for Euclidean TSP",
            "authors": ["A. Author"],
            "year": 1977,
            "venue": "Journal",
            "abstract": "A nearest neighbor tour construction is analysed.",
        }],
    }), encoding="utf-8")
    screen = tmp_path / "screen.json"
    screen.write_text(json.dumps({
        "schema_version": "literature-screen/v1",
        "subproblem_id": "tsp_euclidean",
        "selected": [{
            "doi": "10.1000/tsp-nn",
            "heuristic_name": "Nearest Neighbor",
            "why": "abstract states nearest neighbor construction",
            "steps": ["start at a city", "always go to the nearest unvisited city"],
            "eoh_map": "possible",
            "adapter_kind": "next_node_score",
            "not_the_original": "k-NN truncation is the evaluator contract, not the 1977 paper",
        }],
        "rejected": [],
        "cannot_classify": False,
    }), encoding="utf-8")
    drafts = tmp_path / "drafts"
    result = ingest_screen(queue, screen, drafts)
    assert result["ok"] is True
    method_id = next(item for item in result["written"] if item.startswith("method-"))
    body = (drafts / "entries" / f"{method_id}.md").read_text(encoding="utf-8")
    assert "## EoH 适配" in body
    assert "def select_next_node(current_node: int, start_node: int" in body
    assert "destination_node" not in body
    assert "Plan 只把机制写入" in body

    screen.write_text(json.dumps({
        "schema_version": "literature-screen/v1",
        "subproblem_id": "tsp_euclidean",
        "selected": [{
            "doi": "10.1000/tsp-nn",
            "heuristic_name": "Farthest Insertion",
            "why": "abstract is insertion",
            "steps": ["insert the farthest city into the partial tour"],
            "eoh_map": "not_mappable",
            "adapter_kind": "not_mappable",
            "not_the_original": "insertion is not select_next_node",
        }],
        "rejected": [],
        "cannot_classify": False,
    }), encoding="utf-8")
    drafts2 = tmp_path / "drafts2"
    result = ingest_screen(queue, screen, drafts2)
    method_id = next(item for item in result["written"] if item.startswith("method-"))
    body = (drafts2 / "entries" / f"{method_id}.md").read_text(encoding="utf-8")
    assert "不写 template_program" in body
    assert "def select_next_node" not in body


def test_ingest_without_abstract_is_metadata_only(tmp_path: Path) -> None:
    catalog_item = build_catalog()["families"]["tsp"]["subproblems"][0]
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps({
        "family": "tsp",
        "subproblem": catalog_item,
        "works": [{
            "doi": "10.1000/no-abs",
            "title": "A paper without abstract",
            "authors": ["A. Author"],
            "year": 2001,
            "provider": "crossref",
            "abstract": "",
        }],
    }), encoding="utf-8")
    screen = tmp_path / "screen.json"
    screen.write_text(json.dumps({
        "schema_version": "literature-screen/v1",
        "subproblem_id": "tsp_euclidean",
        "selected": [{
            "doi": "10.1000/no-abs",
            "heuristic_name": "Named Heuristic",
            "why": "seed",
            "steps": ["stated in screen only"],
            "eoh_map": "not_mappable",
            "adapter_kind": "not_mappable",
            "not_the_original": "no abstract",
        }],
        "cannot_classify": False,
    }), encoding="utf-8")
    drafts = tmp_path / "drafts"
    result = ingest_screen(queue, screen, drafts)
    assert result["ok"] is True
    sources = json.loads((drafts / "sources.json").read_text(encoding="utf-8"))
    assert sources["sources"][0]["read_depth"] == "metadata_only"


def test_ingest_cannot_classify_writes_nothing(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps({
        "family": "tsp",
        "subproblem": {"id": "tsp_tw", "label": "TSPTW"},
        "works": [],
    }), encoding="utf-8")
    screen = tmp_path / "screen.json"
    screen.write_text(json.dumps({
        "subproblem_id": "tsp_tw",
        "selected": [],
        "cannot_classify": True,
    }), encoding="utf-8")
    result = ingest_screen(queue, screen, tmp_path / "drafts")
    assert result["skipped"] == "cannot_classify"
    assert result["written"] == []


def test_adapter_signatures_match_registered_entrypoints() -> None:
    tsp = adapter_code("tsp", "next_node_score")
    cvrp = adapter_code("cvrp", "next_node_score")
    obp = adapter_code("online_bin_packing", "bin_score")
    move = adapter_code("tsp", "move_selector")
    assert "start_node: int" in tsp
    assert "depot: int" in cvrp
    assert "rest_capacity: float" in cvrp
    assert "def score(item: float, bins: np.ndarray)" in obp
    assert "def priority(item: float, bins: np.ndarray)" in obp
    assert "def select_2opt_move(" in move
    assert adapter_code("tsp", "not_mappable") is None


def test_whitelist_includes_catalog_and_adapters(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    (workspace / "catalogs").mkdir(parents=True)
    (workspace / "eoh_adapters").mkdir()
    (workspace / "literature_queue" / "tsp").mkdir(parents=True)
    (workspace / "inventory.json").write_text("{}", encoding="utf-8")
    (workspace / "catalogs" / "subproblems.json").write_text("{}\n", encoding="utf-8")
    (workspace / "eoh_adapters" / "bin_score_obp.md").write_text("# adapter\n", encoding="utf-8")
    (workspace / "literature_queue" / "tsp" / "tsp_euclidean.json").write_text("{}\n", encoding="utf-8")
    (workspace / "literature_harvest_scheme.md").write_text("# scheme\n", encoding="utf-8")
    names = {path.name for path in _workspace_whitelist(workspace)}
    assert "subproblems.json" in names
    assert "bin_score_obp.md" in names
    assert "literature_harvest_scheme.md" in names
    assert "tsp_euclidean.json" not in names


def test_validate_requires_eoh_section_when_possible(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    entries = workspace / "entries"
    entries.mkdir(parents=True)
    (workspace / "inventory.json").write_text(json.dumps({"tracked_file_count": 0, "files": []}), encoding="utf-8")
    (workspace / "sources.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    (workspace / "taxonomy.json").write_text(json.dumps({"pages": []}), encoding="utf-8")
    body = "\n".join([
        "# NN",
        "",
        "## 定义或方法步骤",
        "",
        "x",
        "",
        "## 适用条件、假设与限制",
        "",
        "x",
        "",
        "## 来源及支持的具体结论",
        "",
        "x",
        "",
        "## 代码和评测关联",
        "",
        "x",
        "",
        "## 未确认项与冲突证据",
        "",
        "x",
        "",
    ]) + "\n"
    md = entries / "method-lit-nn.md"
    md.write_text(body, encoding="utf-8", newline="\n")
    from knowledge_tools.core import sha256_file
    meta = {
        "id": "method-lit-nn",
        "type": "method",
        "title": "NN",
        "category": "method",
        "problem_family": "tsp",
        "source_refs": [],
        "evidence_refs": ["literature:10.1"],
        "code_refs": [],
        "status": "reviewed",
        "attributes": {"eoh_map": {"status": "possible", "adapter_kind": "next_node_score"}},
        "content_sha256": sha256_file(md),
    }
    (entries / "method-lit-nn.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    result = validate_workspace(workspace)
    assert result["ok"] is False
    assert any("EoH 适配" in item for item in result["errors"])


def test_write_adapter_files(tmp_path: Path) -> None:
    result = write_adapter_files(tmp_path)
    assert result["ok"] is True
    text = (tmp_path / "next_node_score_tsp.md").read_text(encoding="utf-8")
    assert "tsp_construct" in text
    assert "plan.json" in text.lower() or "Plan JSON" in text


def test_family_batch_skips_screened_and_splits(tmp_path: Path) -> None:
    catalog = build_catalog()["families"]["tsp"]["subproblems"]
    queue = tmp_path / "tsp"
    queue.mkdir()
    for item in catalog[:2]:
        (queue / f"{item['id']}.json").write_text(json.dumps({
            "family": "tsp",
            "subproblem": item,
            "works": [{
                "doi": f"10.1000/{item['id']}",
                "year": 2000,
                "title": item["label"],
                "authors": ["A"],
                "abstract": "Nearest neighbor construction is described.",
                "cited_by_count": 3,
            }],
        }), encoding="utf-8")
    (queue / "tsp_euclidean.screen.json").write_text("{}", encoding="utf-8")
    prompt = tmp_path / "batch.md"
    packed = pack_family_batch(queue, prompt)
    assert packed["subproblem_ids"] == ["tsp_asymmetric"]
    text = prompt.read_text(encoding="utf-8")
    assert "tsp_asymmetric" in text
    assert "tsp_euclidean" not in text
    assert "Do not use tools" in text
    batch = {
        "schema_version": "literature-screen-batch/v1",
        "family": "tsp",
        "screens": [{
            "schema_version": "literature-screen/v1",
            "subproblem_id": "tsp_asymmetric",
            "selected": [{
                "doi": "10.1000/tsp_asymmetric",
                "heuristic_name": "Directed NN",
                "why": "abstract states NN",
                "steps": ["go to nearest unused city"],
                "eoh_map": "possible",
                "adapter_kind": "next_node_score",
                "not_the_original": "directed distances",
            }],
            "rejected": [],
            "cannot_classify": False,
        }],
    }
    split = split_batch_screen(batch, queue)
    assert split["ok"] is True
    assert (queue / "tsp_asymmetric.screen.json").exists()


def test_refresh_rewrites_low_abstract_queue(tmp_path: Path) -> None:
    catalog = build_catalog()
    out = tmp_path / "queue"
    family = out / "tsp"
    family.mkdir(parents=True)
    sid = catalog["families"]["tsp"]["subproblems"][1]["id"]
    target = family / f"{sid}.json"
    target.write_text(json.dumps({
        "family": "tsp",
        "subproblem": catalog["families"]["tsp"]["subproblems"][1],
        "works": [{"doi": "10.0/old", "title": "old", "abstract": None}],
    }), encoding="utf-8")
    screen = family / f"{sid}.screen.json"
    screen.write_text(json.dumps({
        "subproblem_id": sid,
        "selected": [],
        "cannot_classify": True,
    }), encoding="utf-8")
    calls = []

    def fake_search(query: str, rows: int, mailto: str | None):
        calls.append(query)
        return [{
            "doi": "10.0/new",
            "title": "new",
            "authors": ["A"],
            "year": 2001,
            "abstract": "Directed nearest neighbor on an asymmetric matrix.",
            "abstract_missing": False,
        }]

    result = harvest_catalog(
        catalog, out, family="tsp", only_ids=[sid],
        refresh_if_abstracts_lt=1, pause_seconds=0, search=fake_search,
    )
    assert result["written"] == 1
    assert not screen.exists()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["works"][0]["doi"] == "10.0/new"


def test_pack_requires_abstract_and_skips_classified(tmp_path: Path) -> None:
    catalog = build_catalog()["families"]["tsp"]["subproblems"]
    queue = tmp_path / "q"
    (queue / "tsp").mkdir(parents=True)
    eu, asym, metric = catalog[0], catalog[1], catalog[2]
    (queue / "tsp" / f"{eu['id']}.json").write_text(json.dumps({
        "family": "tsp", "subproblem": eu,
        "works": [{"doi": "10.1", "abstract": "NN steps", "cited_by_count": 1}],
    }), encoding="utf-8")
    (queue / "tsp" / f"{eu['id']}.screen.json").write_text(json.dumps({
        "selected": [{"doi": "10.1", "heuristic_name": "NN", "steps": ["x"],
                      "eoh_map": "possible", "adapter_kind": "next_node_score"}],
        "cannot_classify": False,
    }), encoding="utf-8")
    (queue / "tsp" / f"{asym['id']}.json").write_text(json.dumps({
        "family": "tsp", "subproblem": asym,
        "works": [{"doi": "10.2", "abstract": None}],
    }), encoding="utf-8")
    (queue / "tsp" / f"{metric['id']}.json").write_text(json.dumps({
        "family": "tsp", "subproblem": metric,
        "works": [{"doi": "10.3", "abstract": "Christofides matching then shortcuts.", "cited_by_count": 9}],
    }), encoding="utf-8")
    packed = pack_family_batch(
        queue, tmp_path / "batch.md",
        skip_screened=False, skip_classified=True, require_abstract=True,
    )
    assert packed["subproblem_ids"] == ["tsp_metric"]
    assert packed["skipped_classified"] == 1
    assert packed["skipped_no_abstract"] == 1
