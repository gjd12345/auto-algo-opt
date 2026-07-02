import tempfile
import unittest
from pathlib import Path


class RagSchemasTests(unittest.TestCase):
    def test_jsonl_roundtrip_preserves_corpus_item_fields(self) -> None:
        from eoh_rag.rag.schemas import CorpusItem, load_corpus, save_corpus

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "items.jsonl"
            items = [
                CorpusItem(
                    id="topk_delta",
                    kind="algorithm_card",
                    title="Top-k delta insertion",
                    tags=["insertships", "delta"],
                    source_path="source.txt",
                    summary="Choose the lowest feasible insertion delta.",
                    constraints=["Rollback failed tentative insertions"],
                    content="pseudo-code",
                )
            ]

            save_corpus(items, path)
            loaded = load_corpus(path)

        self.assertEqual(loaded, items)

    def test_load_missing_or_empty_corpus_returns_empty_list(self) -> None:
        from eoh_rag.rag.schemas import load_corpus

        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.jsonl"
            empty = Path(tmp) / "empty.jsonl"
            empty.write_text("", encoding="utf-8")

            self.assertEqual(load_corpus(missing), [])
            self.assertEqual(load_corpus(empty), [])


if __name__ == "__main__":
    unittest.main()
