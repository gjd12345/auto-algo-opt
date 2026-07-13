"""冻结 Q3 机制实验的等卡槽、等长度上下文。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS_PATH = REPOSITORY_ROOT / "eoh_rag_workspace/rag/corpus/algorithm_cards.jsonl"
DEFAULT_OUTPUT_DIR = REPOSITORY_ROOT / "eoh_rag_workspace/experiments/strategies/q3_mechanism"
SLOT_WIDTH = 900
CONTEXT_HEADER = (
    "CONTROLLED STRATEGY CONTEXT\n"
    "The following section always contains exactly two card slots. "
    "Use strategy content only when a slot explicitly provides it.\n\n"
)
NEUTRAL_PADDING = "This padding only equalizes context length and adds no task rule. "
SHAM_BODY = (
    "Type: control slot\n"
    "Purpose: preserve the two-slot format without providing a strategy.\n"
    "Content: no task-specific scoring rule, threshold, formula, ordering, or implementation hint is present.\n"
    "Instruction: ignore this slot when designing the heuristic."
)


def _read_cards(corpus_path: Path) -> dict[str, dict]:
    """读取本轮需要的两张原始卡，避免复制语义时与语料库漂移。"""
    required_ids = {"obp_harmonic", "obp_funsearch_residual_poly"}
    cards: dict[str, dict] = {}
    for line in corpus_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("id") in required_ids:
            cards[row["id"]] = row
    missing = sorted(required_ids - cards.keys())
    if missing:
        raise ValueError(f"missing source cards: {missing}")
    return cards


def _card_body(card: dict) -> str:
    """只保留标题、摘要、约束和正文，去掉检索分数等运行时信息。"""
    constraints = "\n".join(f"- {item}" for item in card.get("constraints", []))
    return (
        f"Type: frozen strategy\n"
        f"Title: {card['title']}\n"
        f"Summary: {card['summary']}\n"
        f"Constraints:\n{constraints}\n"
        f"Strategy:\n{card['content']}"
    )


def _fused_body(harmonic: dict, residual: dict) -> str:
    """把两张卡压成一个语义单元，用于区分“语义整合”和“两卡格式”。"""
    return (
        "Type: frozen fused strategy\n"
        "Title: Size-class residual scoring\n"
        "Summary: first classify the item by relative size, then score feasible bins with a stable residual rule.\n"
        "Strategy:\n"
        "Use the item-to-capacity ratio to choose a simple regime. Large items favor tight fits. "
        "Medium items avoid residual gaps that are too small to reuse. Small items preserve useful medium gaps. "
        "Within each regime, compute residual after placement, reward exact or tight fits, and apply a bounded "
        "nonlinear penalty to isolated tiny gaps. Keep every score finite, deterministic, and vectorized.\n"
        "Fallback: use a deterministic tight-fit score when regimes tie.\n"
        "Safety: do not use future items, randomness, files, environment variables, or network access.\n"
        f"Source cards: {harmonic['id']} and {residual['id']}."
    )


def _build_slot(slot_number: int, body: str) -> str:
    """将每个卡槽填充到固定字符数，消除卡槽长度差异。"""
    prefix = f"[CARD SLOT {slot_number}]\n"
    suffix = f"\n[END CARD SLOT {slot_number}]"
    base = prefix + body.strip() + "\n[NEUTRAL LENGTH PADDING]\n" + suffix
    remaining = SLOT_WIDTH - len(base)
    if remaining < 0:
        raise ValueError(f"slot {slot_number} exceeds {SLOT_WIDTH} characters")
    repeated = (NEUTRAL_PADDING * ((remaining // len(NEUTRAL_PADDING)) + 1))[:remaining]
    return prefix + body.strip() + "\n[NEUTRAL LENGTH PADDING]\n" + repeated + suffix


def build_contexts(corpus_path: Path = DEFAULT_CORPUS_PATH) -> dict[str, str]:
    """返回五份固定上下文；pure 与 api-only 不需要上下文文件。"""
    cards = _read_cards(corpus_path)
    harmonic = _card_body(cards["obp_harmonic"])
    residual = _card_body(cards["obp_funsearch_residual_poly"])
    fused = _fused_body(cards["obp_harmonic"], cards["obp_funsearch_residual_poly"])
    slots = {
        "sham_sham": (SHAM_BODY, SHAM_BODY),
        "harmonic_sham": (harmonic, SHAM_BODY),
        "sham_residual": (SHAM_BODY, residual),
        "harmonic_residual": (harmonic, residual),
        "fused_sham": (fused, SHAM_BODY),
    }
    return {
        name: CONTEXT_HEADER + _build_slot(1, first) + "\n\n" + _build_slot(2, second) + "\n"
        for name, (first, second) in slots.items()
    }


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def freeze_contexts(output_dir: Path, corpus_path: Path = DEFAULT_CORPUS_PATH) -> dict:
    """写出上下文和整体锁文件，正式实验只读取这些冻结产物。"""
    contexts = build_contexts(corpus_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    lengths = {len(value) for value in contexts.values()}
    if len(lengths) != 1:
        raise AssertionError(f"context lengths differ: {sorted(lengths)}")

    files: dict[str, dict] = {}
    for name, value in contexts.items():
        path = output_dir / f"{name}.txt"
        path.write_text(value, encoding="utf-8")
        files[path.name] = {"chars": len(value), "sha256": _sha256_text(value)}

    cards = _read_cards(corpus_path)
    source_hashes = {
        card_id: _sha256_text(json.dumps(card, ensure_ascii=False, sort_keys=True))
        for card_id, card in sorted(cards.items())
    }
    lock = {
        "schema_version": "q3-mechanism-context-lock/v1",
        "slot_count": 2,
        "slot_chars": SLOT_WIDTH,
        "context_chars": lengths.pop(),
        "effective_context_chars": len(next(iter(contexts.values())).strip()),
        "source_card_sha256": source_hashes,
        "files": files,
    }
    (output_dir / "context_lock.json").write_text(
        json.dumps(lock, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return lock


def validate_frozen_contexts(lock_path: Path) -> dict:
    """核对每份冻结上下文的长度与哈希，防止正式运行前文件被静默修改。"""
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for filename, metadata in lock.get("files", {}).items():
        path = lock_path.parent / filename
        if not path.is_file():
            errors.append(f"missing context file: {filename}")
            continue
        value = path.read_text(encoding="utf-8")
        if len(value) != metadata.get("chars"):
            errors.append(f"context length mismatch: {filename}")
        if _sha256_text(value) != metadata.get("sha256"):
            errors.append(f"context sha256 mismatch: {filename}")
        if value.count("[CARD SLOT ") != lock.get("slot_count"):
            errors.append(f"context slot count mismatch: {filename}")
    if errors:
        raise ValueError("; ".join(errors))
    return lock


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    args = parser.parse_args()
    print(json.dumps(freeze_contexts(args.output_dir, args.corpus), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
