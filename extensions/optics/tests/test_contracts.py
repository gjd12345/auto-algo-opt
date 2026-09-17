"""Small P1 contract checks; no provider or optical execution."""

import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from optics_backend.artifacts import canonical, extract_response, strict
from optics_backend.ranking import audit_eligible, compare, rank_key
from optics_backend.offline import evaluate


def facts(passed, q, margin):
    return {"mode": "online", "submission_status": "valid", "execution_status": "complete",
            "physics_status": "OK", "constraint_ids": ["c"], "quality_q": q,
            "constraints": {"c": {"passed": passed, "ranking_included": True, "normalized_margin": margin}},
            "online_feasible": passed, "evaluation_identity": {"task": "t1", "canonical_artifact_sha256": str(q)}}


class Contracts(unittest.TestCase):
    def test_raw_span_and_canonical_identity(self):
        raw = '{"description":"中文\\\"与括号}", "prescription": { "x": [1, {"a":"\\\"}"}] }}'.encode()
        fragment, receipt = extract_response(raw)
        self.assertEqual(fragment, raw[receipt["start_byte"]:receipt["end_byte"]])
        self.assertTrue(fragment.startswith(b'{ "x"'))
        self.assertEqual(strict(fragment), strict(raw)["prescription"])
        self.assertEqual(canonical({"b": 2, "a": 1}), canonical({"a": 1, "b": 2}))
        self.assertNotEqual(canonical({"a": 1}), canonical({"a": 1.0}))

    def test_strict_rejections(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b'{} {}', b'[' * 65 + b']' * 65):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                strict(raw)
        with self.assertRaises(ValueError):
            extract_response(b'{"description":"x","prescription":{"a":1,"a":2}}')

    def test_s1_and_eligibility_are_distinct(self):
        bad = facts(False, .99, -.1)
        good = facts(True, .1, .1)
        self.assertIsNotNone(rank_key(bad))
        self.assertFalse(audit_eligible(bad))
        self.assertTrue(audit_eligible(good))
        self.assertEqual(compare(bad, good)["decision"], "accept")
        self.assertEqual(compare(good, good)["decision"], "retain")
        unknown = copy.deepcopy(good)
        unknown["physics_status"] = "NUMERICAL_UNCERTAIN"
        self.assertIsNone(rank_key(unknown))
        self.assertEqual(compare(good, unknown)["decision"], "incomparable")

    def test_comparison_identity(self):
        one, two = facts(True, .1, .1), facts(True, .2, .1)
        two["evaluation_identity"]["task"] = "t3"
        with self.assertRaisesRegex(ValueError, "IDENTITY_MISMATCH"):
            compare(one, two)

    def test_ranking_survives_json_key_reordering(self):
        one = facts(False, .1, -1.0)
        row = one["constraints"]["c"]
        one["constraints"] = {"z": {**row, "normalized_margin": -1e16}, "b": dict(row), "a": dict(row)}
        one["constraint_ids"] = ["z", "b", "a"]
        self.assertEqual(rank_key(one), rank_key(strict(canonical(one))))
        self.assertEqual(rank_key(one)[1], -10000000000000002.0)

    def test_output_ownership_and_timeout_preflight(self):
        with tempfile.TemporaryDirectory() as temp, patch("optics_backend.offline.load_task"), patch("optics_backend.offline.subprocess.run") as run:
            output = Path(temp) / "existing"
            output.mkdir()
            sentinel = output / "worker.stdout"
            sentinel.write_bytes(b"previous owner's evidence")
            with self.assertRaisesRegex(ValueError, "OUTPUT_EXISTS"):
                evaluate(Path(temp), "task", Path(temp) / "input", output)
            self.assertEqual(sentinel.read_bytes(), b"previous owner's evidence")
            for timeout in (0, -1, float("nan"), float("inf")):
                with self.assertRaisesRegex(ValueError, "TIMEOUT"):
                    evaluate(Path(temp), "task", Path(temp) / "input", Path(temp) / "new", timeout=timeout)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
