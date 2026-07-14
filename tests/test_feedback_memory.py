from __future__ import annotations

import hashlib
import json
from pathlib import Path

from eoh_rag.experiments.feedback_memory import (
    build_feedback_cards,
    collect_dev_samples,
)
from eoh_rag.experiments.batch_runner import _build_cmd, _validate_manifest
from eoh_rag.experiments.rag_context_builder import build_official_rag_context
from eoh_rag.rag.schemas import save_corpus


def _write_samples(report_dir: Path, seed: int, rows: list[dict]) -> None:
    path = (
        report_dir
        / "tsp_search_controller"
        / "eoh_controller"
        / str(seed)
        / "results"
        / "samples"
        / "samples_1~2.json"
    )
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(rows), encoding="utf-8")


def test_feedback_memory_reads_only_samples_and_drops_code(tmp_path: Path) -> None:
    report_dir = tmp_path / "proxy_v1"
    _write_samples(
        report_dir,
        1,
        [
            {
                "sample_order": 1,
                "operator": "e1",
                "algorithm": "size-aware schedule",
                "code": "def build_search_plan(...): secret_body",
                "objective": 0.84,
            },
            {
                "sample_order": 2,
                "operator": "m1",
                "algorithm": None,
                "code": None,
                "objective": None,
            },
        ],
    )
    # 即使同一 run 有 held-out 文件，反馈生成器也没有读取该路径的入口。
    held_out = report_dir / "tsp_search_controller" / "eoh_controller" / "1" / "held_out_report.json"
    held_out.write_text('{"secret_confirm_metric": 0.1}', encoding="utf-8")

    records = collect_dev_samples([report_dir])
    cards = build_feedback_cards(
        records,
        problem="tsp_search_controller",
        baseline_objective=0.82903,
        asset_version="test_v1",
    )

    serialized = json.dumps([card.to_dict() for card in cards], ensure_ascii=False)
    assert len(records) == 2
    assert "secret_body" not in serialized
    assert "secret_confirm_metric" not in serialized
    assert len(cards) == 4


def test_extra_feedback_corpus_is_retrieved_and_traced(tmp_path: Path) -> None:
    records = [
        {
            "suite": "proxy_v1",
            "run": "run/1",
            "sample_order": 1,
            "operator": "e1",
            "has_code": True,
            "objective": 0.84,
            "algorithm": "size-aware weighted budget controller",
        }
    ]
    cards = build_feedback_cards(
        records,
        problem="tsp_search_controller",
        baseline_objective=0.82903,
        asset_version="test_v2",
    )
    corpus_path = tmp_path / "feedback.jsonl"
    save_corpus(cards, corpus_path)

    context, trace = build_official_rag_context(
        Path.cwd(),
        "tsp_search_controller",
        "history_rag",
        top_k=2,
        max_chars=1800,
        candidate_card_ids=[card.id for card in cards],
        extra_corpus_paths=(str(corpus_path),),
    )

    assert "RETRIEVED STRATEGY CARDS" in context
    assert trace["rag_extra_corpus_item_count"] == 4
    assert trace["rag_extra_corpus_paths"] == [str(corpus_path.resolve())]
    assert len(trace["rag_selected_items"]) == 2


def test_feedback_rag_proxy_manifest_is_paired_and_passes_extra_corpus() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (
            repo_root
            / "eoh_rag_workspace/experiments/manifests/tsp_search_controller_feedback_rag_proxy_v1.json"
        ).read_text(encoding="utf-8")
    )

    assert _validate_manifest(manifest) == []
    assert manifest["seed_list"] == [9401, 9402, 9403]
    memory_path = (
        repo_root
        / "eoh_rag_workspace/experiments/assets/tsp_search_controller_feedback_v1.jsonl"
    )
    assert hashlib.sha256(memory_path.read_bytes()).hexdigest().upper() == manifest[
        "feedback_memory"
    ]["sha256"]
    feedback_arm = next(arm for arm in manifest["arms"] if arm["name"] == "feedback_rag")
    command = _build_cmd(
        manifest,
        "tsp_search_controller",
        feedback_arm,
        2,
        1,
        "feedback-output",
        seed=9401,
    )
    corpus_path = Path(command[command.index("--rag-extra-corpus") + 1])
    assert corpus_path == memory_path.resolve()
    assert command[command.index("--controller-budget-policy") + 1] == "clip"
