"""从现有卡片与 outcome 摘要构建 dev-only FME 冷启动快照。"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from eoh_rag.fme.cold_start import HistoricalEvidenceItem


MAINLINE = ("bp_online", "tsp_construct", "cvrp_construct")


def _jsonl(path: Path):
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def _problem_from_card(card: dict) -> str | None:
    haystack = " ".join(
        str(value).lower()
        for value in (card.get("id"), card.get("title"), card.get("summary"), card.get("tags"))
    )
    aliases = {
        "bp_online": ("bp_online", "bin packing", "bin_packing"),
        "tsp_construct": ("tsp", "traveling salesman"),
        "cvrp_construct": ("cvrp", "vehicle routing"),
    }
    matches = [problem for problem, terms in aliases.items() if any(term in haystack for term in terms)]
    return matches[0] if len(matches) == 1 else None


def build(corpus_dir: Path) -> list[HistoricalEvidenceItem]:
    items: list[HistoricalEvidenceItem] = []
    for card in _jsonl(corpus_dir / "algorithm_cards.jsonl") or ():
        problem = _problem_from_card(card)
        if problem not in MAINLINE:
            continue
        text = f"{card.get('title', '')}: {card.get('summary', '')}. {card.get('content', '')}".strip()
        items.append(
            HistoricalEvidenceItem.create(
                item_id=f"literature:{card.get('id')}",
                text=text,
                source_kind="literature",
                source_problem=problem,
                contains_executable_code="```" in text or "def " in text,
            )
        )
    for failure in _jsonl(corpus_dir / "failure_cases.jsonl") or ():
        text = f"{failure.get('title', '')}: {failure.get('summary', '')}. {failure.get('content', '')}".strip()
        items.append(
            HistoricalEvidenceItem.create(
                item_id=f"failure:{failure.get('id')}",
                text=text,
                source_kind="failure",
                source_problem="shared",
            )
        )
    seen_outcomes: set[tuple[str, str, str]] = set()
    for outcome in _jsonl(corpus_dir / "card_outcomes.jsonl") or ():
        problem = str(outcome.get("problem", ""))
        if problem not in MAINLINE or "held" in json.dumps(outcome).lower():
            continue
        key = (problem, str(outcome.get("card_id", "")), str(outcome.get("decision_hint", "")))
        if key in seen_outcomes:
            continue
        seen_outcomes.add(key)
        text = (
            f"历史进化结果：卡片 {key[1]} 在 {problem} 的 dev 记录为 {key[2] or 'unknown'}；"
            f"valid_rate={outcome.get('valid_rate')}; failure={outcome.get('failure_reason') or 'none'}。"
        )
        items.append(
            HistoricalEvidenceItem.create(
                item_id=f"evolution:{problem}:{key[1]}:{key[2] or 'unknown'}",
                text=text,
                source_kind="evolution",
                source_problem=problem,
            )
        )
    return sorted(items, key=lambda item: item.item_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-dir", type=Path, default=Path("eoh_rag_workspace/rag/corpus"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    items = build(args.corpus_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(asdict(item), ensure_ascii=False, sort_keys=True) + "\n" for item in items)
    args.output.write_text(body, encoding="utf-8")
    counts: dict[str, int] = {}
    for item in items:
        counts[item.source_kind] = counts.get(item.source_kind, 0) + 1
    manifest = {
        "schema_version": "fme_cold_start_snapshot/v1",
        "snapshot_id": "refactor0830_cold_start_v1",
        "visible_scope": "dev_only",
        "item_count": len(items),
        "counts_by_kind": counts,
        "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "source_files": ["algorithm_cards.jsonl", "failure_cases.jsonl", "card_outcomes.jsonl"],
        "heldout_included": False,
        "executable_cross_problem_transfer_allowed": False,
    }
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
