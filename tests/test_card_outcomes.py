"""Tests for card_outcomes.py — Card Outcome Memory evidence layer."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from eoh_rag.rag.card_outcomes import (
    CardOutcomeRecord,
    CardOutcomeSummary,
    build_outcome_records,
    compute_card_set_id,
    compute_decision_hint,
    load_outcomes,
    save_outcomes,
    summarize_all_cards,
    summarize_card,
)


class CardOutcomeTests(unittest.TestCase):

    def _make_audit(self, card_ids=None, truncated_id=None):
        """Build a minimal injection audit dict."""
        card_ids = card_ids or ["regret_insertion", "far_first"]
        items = []
        for cid in card_ids:
            status = "truncated" if cid == truncated_id else "full"
            items.append({"id": cid, "kind": "algorithm_card", "section": "strategy", "status": status, "chars": 400})
        omitted = []
        return {
            "rag_injected_items": items,
            "rag_omitted_items": omitted,
            "rag_truncated_item_id": truncated_id,
            "rag_context_truncated": truncated_id is not None,
        }

    def _make_gen_result(self, pop=8, valid=6, best=12.5, baseline=14.0, failure=None):
        return {
            "population_size": pop,
            "valid_candidates": valid,
            "best_objective": best,
            "pure_baseline": baseline,
            "failure_reason": failure,
        }

    # ── compute_card_set_id ──

    def test_card_set_id_is_order_independent(self) -> None:
        id1 = compute_card_set_id(["a", "b", "c"])
        id2 = compute_card_set_id(["c", "a", "b"])
        self.assertEqual(id1, id2)

    def test_card_set_id_differs_for_different_sets(self) -> None:
        id1 = compute_card_set_id(["a", "b"])
        id2 = compute_card_set_id(["a", "c"])
        self.assertNotEqual(id1, id2)

    # ── compute_decision_hint ──

    def test_decision_positive(self) -> None:
        self.assertEqual(compute_decision_hint(True, True, 0.8, None), "positive")

    def test_decision_negative_collapse(self) -> None:
        self.assertEqual(compute_decision_hint(True, True, 0.8, "valid_collapse"), "negative")

    def test_decision_negative_low_valid_rate(self) -> None:
        self.assertEqual(compute_decision_hint(True, False, 0.2, None), "negative")

    def test_decision_neutral(self) -> None:
        self.assertEqual(compute_decision_hint(True, False, 0.5, None), "neutral")

    # ── build_outcome_records ──

    def test_build_records_creates_one_per_injected_card(self) -> None:
        audit = self._make_audit(["card_a", "card_b"])
        gen_result = self._make_gen_result()
        records = build_outcome_records(
            run_id="run_001", problem="tsp_construct", generation=1,
            injection_audit=audit, generation_result=gen_result,
        )
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].card_id, "card_a")
        self.assertEqual(records[0].card_rank, 1)
        self.assertEqual(records[1].card_id, "card_b")
        self.assertEqual(records[1].card_rank, 2)

    def test_build_records_shares_card_set_id(self) -> None:
        audit = self._make_audit(["card_a", "card_b"])
        gen_result = self._make_gen_result()
        records = build_outcome_records(
            run_id="run_001", problem="tsp_construct", generation=1,
            injection_audit=audit, generation_result=gen_result,
        )
        self.assertEqual(records[0].card_set_id, records[1].card_set_id)
        self.assertNotEqual(records[0].card_set_id, "")

    def test_build_records_computes_delta_pct(self) -> None:
        audit = self._make_audit(["card_a"])
        gen_result = self._make_gen_result(best=12.0, baseline=14.0)
        records = build_outcome_records(
            run_id="run_001", problem="tsp_construct", generation=1,
            injection_audit=audit, generation_result=gen_result,
        )
        self.assertAlmostEqual(records[0].delta_pct, -14.29, places=1)

    def test_build_records_marks_truncated_status(self) -> None:
        audit = self._make_audit(["card_a", "card_b"], truncated_id="card_b")
        gen_result = self._make_gen_result()
        records = build_outcome_records(
            run_id="run_001", problem="tsp_construct", generation=1,
            injection_audit=audit, generation_result=gen_result,
        )
        self.assertEqual(records[1].injection_status, "truncated")

    def test_build_records_includes_omitted(self) -> None:
        audit = self._make_audit(["card_a"])
        audit["rag_omitted_items"] = [{"id": "card_z", "reason": "budget_exceeded"}]
        gen_result = self._make_gen_result()
        records = build_outcome_records(
            run_id="run_001", problem="tsp_construct", generation=1,
            injection_audit=audit, generation_result=gen_result,
        )
        self.assertEqual(len(records), 2)
        omitted_record = next(r for r in records if r.card_id == "card_z")
        self.assertEqual(omitted_record.injection_status, "omitted")
        self.assertEqual(omitted_record.card_rank, 0)

    def test_build_records_identifies_history_source(self) -> None:
        audit = self._make_audit(["history_tsp_regret_abc123"])
        gen_result = self._make_gen_result()
        records = build_outcome_records(
            run_id="run_001", problem="tsp_construct", generation=1,
            injection_audit=audit, generation_result=gen_result,
        )
        self.assertEqual(records[0].card_source, "history")

    # ── save/load persistence ──

    def test_save_and_load_roundtrip(self) -> None:
        audit = self._make_audit(["card_a", "card_b"])
        gen_result = self._make_gen_result()
        records = build_outcome_records(
            run_id="run_001", problem="tsp_construct", generation=1,
            injection_audit=audit, generation_result=gen_result,
            timestamp="2026-06-26T10:00:00",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "outcomes.jsonl"
            save_outcomes(records, path)
            loaded = load_outcomes(path)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0].card_id, "card_a")
            self.assertEqual(loaded[0].run_id, "run_001")
            self.assertEqual(loaded[0].timestamp, "2026-06-26T10:00:00")

    def test_save_append_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "outcomes.jsonl"
            audit = self._make_audit(["card_a"])
            gen_result = self._make_gen_result()
            r1 = build_outcome_records("run_001", "tsp", 1, audit, gen_result)
            r2 = build_outcome_records("run_002", "tsp", 2, audit, gen_result)
            save_outcomes(r1, path)
            save_outcomes(r2, path, append=True)
            loaded = load_outcomes(path)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0].run_id, "run_001")
            self.assertEqual(loaded[1].run_id, "run_002")

    def test_save_is_idempotent(self) -> None:
        """Re-running summarizer on same data should not duplicate rows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "outcomes.jsonl"
            audit = self._make_audit(["card_a", "card_b"])
            gen_result = self._make_gen_result()
            records = build_outcome_records("run_001", "tsp", 1, audit, gen_result)
            save_outcomes(records, path)
            save_outcomes(records, path, append=True)  # second write = same data
            save_outcomes(records, path, append=True)  # third write
            loaded = load_outcomes(path)
            self.assertEqual(len(loaded), 2)  # still only 2, not 6

    # ── summarize_card ──

    def test_summarize_positive_card(self) -> None:
        records = []
        for i in range(4):
            records.append(CardOutcomeRecord(
                card_id="good_card", injection_status="full",
                card_set_id=f"set_{i}", valid_rate=0.8,
                delta_pct=-10.0, decision_hint="positive",
            ))
        summary = summarize_card("good_card", records)
        self.assertEqual(summary.decision, "boost")
        self.assertEqual(summary.positive_count, 4)
        self.assertEqual(summary.total_injections, 4)
        self.assertEqual(summary.as_set_member_runs, 4)

    def test_summarize_negative_card(self) -> None:
        records = []
        for i in range(3):
            records.append(CardOutcomeRecord(
                card_id="bad_card", injection_status="full",
                card_set_id=f"set_{i}", valid_rate=0.2,
                decision_hint="negative", failure_reason="valid_collapse",
            ))
        summary = summarize_card("bad_card", records)
        self.assertEqual(summary.decision, "suppress")
        self.assertEqual(summary.collapse_count, 3)

    def test_summarize_ignores_omitted(self) -> None:
        records = [
            CardOutcomeRecord(card_id="x", injection_status="omitted", decision_hint="negative"),
            CardOutcomeRecord(card_id="x", injection_status="full", card_set_id="s1",
                             valid_rate=0.9, decision_hint="positive"),
        ]
        summary = summarize_card("x", records)
        self.assertEqual(summary.total_injections, 1)
        self.assertEqual(summary.decision, "neutral")

    def test_summarize_all_cards(self) -> None:
        records = [
            CardOutcomeRecord(card_id="a", injection_status="full", card_set_id="s1",
                             valid_rate=0.9, decision_hint="positive"),
            CardOutcomeRecord(card_id="b", injection_status="full", card_set_id="s1",
                             valid_rate=0.9, decision_hint="positive"),
        ]
        summaries = summarize_all_cards(records)
        self.assertIn("a", summaries)
        self.assertIn("b", summaries)


if __name__ == "__main__":
    unittest.main()
