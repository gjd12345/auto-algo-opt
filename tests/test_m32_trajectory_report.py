from __future__ import annotations

import json
import re

import pytest

from tools import build_m32_trajectory_report as report


def test_recorded_experiment_reconciles_and_renders_safely():
    payload = report.build_payload()
    assert payload["kpis"] == {
        "locked": 21, "expected": 21, "requests": 4800,
        "priced": 4257, "unpriced": 543, "cost": pytest.approx(4.84189081),
    }
    assert len(payload["runs"]) == 12
    assert len(payload["blind"]) == 25

    curve = {run["seed"]: run for run in payload["runs"] if run["track"] == "curve"}
    first = curve[20261124]
    assert [(c["budget"], c["ordinal"]) for c in first["checkpoints"]] == [
        (36, 29), (100, 51), (200, 152), (400, 319),
    ]
    assert curve[20261126]["checkpoints"][0]["ordinal"] == 0
    for run in payload["runs"]:
        scores = [score for _, score in run["envelope"]]
        assert all(new < old for old, new in zip(scores, scores[1:]))
        assert all([c["ordinal"], c["objective"]] in run["envelope"] for c in run["checkpoints"])
        assert run["rounds"][-1]["end"] == 400
    assert any(req["outcome"] is None and req["state"] != "complete" for req in first["requests"])

    for seed, timeout in zip(report.SEEDS, (40, 40, 33), strict=True):
        short = payload["blind"][f"{seed}:checkpoint:400"]["sizes"]
        assert [short[n]["completed"] for n in ("n50", "n100")] == [40, 40]
        assert short["n200"]["timeouts"] == timeout
        assert short["n200"]["feasible"] == 40
        long = payload["blind"][f"{seed}:control:timeout_2000ms"]["overall"]
        assert (long["n"], long["timeouts"], long["within"]) == (120, 0, 120)
    comparator = payload["blind"]["l3_ctrl@500ms"]["overall"]
    assert (comparator["completed"], comparator["within"], comparator["timeouts"]) == (120, 111, 9)
    assert comparator["strict"] > comparator["penalized"]

    stats = payload["stats"]
    assert (sum(s["family"] == "published" for s in stats), sum(s["family"] == "baseline" for s in stats)) == (12, 6)
    assert all(sum(s["wtl"]) == s["n"] == 120 for s in stats)
    matched = [s for s in stats if s["reference"] == "l3_ctrl@2000ms"]
    assert len(matched) == 3 and all(s["gain"] > 0 and s["pHolm"] < .05 for s in matched)
    assert matched[0]["wtl"] == [116, 2, 2]
    assert len(payload["operators"]) == 12
    assert {row["solver"] for row in payload["operators"]} >= {"ckpt_cand_8c4dfb41aa", "ckpt_cand_22af9ec1ab"}

    document = report.render_html(payload)
    match = re.search(r'<script type="application/json" id="m32-data">(.*?)</script>', document, re.DOTALL)
    assert match and json.loads(match[1]) == payload
    assert report.FORBIDDEN.search(document) is None
    assert not re.search(r'<(?:script|link|iframe|img)\b[^>]+\b(?:src|href)\s*=', document, re.IGNORECASE)
    assert "connect-src 'none'" in document


def test_zero_missing_and_timeout_semantics():
    fixture = {
        "instance_id": "m32blind_n50_uniform_centre_loose_uniform-000",
        "objective": 0, "reference_objective": 8, "solve_ms": 0,
        "feasible": True, "completed": True, "exact_k_feasible": True,
        "sealed_seed_token": "TOKEN_SENTINEL", "demands": [763221], "raw_coordinates": [[391427, 119374]],
    }
    zero = report._blind_record(fixture)
    timeout = report._blind_record(dict(fixture, objective=3, solve_ms=500, completed=False, budget_exhausted=True))
    missing = report._blind_record(dict(fixture, objective=None, solve_ms=None, feasible=False))
    stats = report._metrics([zero, timeout, missing], 500)
    assert (stats["n"], stats["within"], stats["feasible"], stats["timeouts"]) == (3, 1, 2, 1)
    assert stats["raw"] == 1.5
    assert stats["completedMean"] == 0
    assert stats["penalized"] == pytest.approx(32 / 3)
    assert stats["solve"]["p10"] == 50
    assert stats["solve"]["p50"] == 250
    assert stats["solve"]["max"] == 500
    assert stats["under500"] == 2
    assert report._metrics([missing], 500)["solve"]["p50"] is None
    assert report._metrics([missing], 500)["raw"] is None
    code = "def score_ruin_nodes():\n    return 959591"
    loc = report._hook_locs({"hook_name": "score_ruin_nodes", "hook_code": code})
    assert loc == {"score_ruin_nodes": 2}
    document = report.render_html({"aggregate": stats, "loc": loc})
    for sentinel in (fixture["instance_id"], "TOKEN_SENTINEL", "763221", "391427", "959591"):
        assert sentinel not in document


def test_inline_json_escapes_script_boundaries_and_rejects_leaks():
    value = "</ScRiPt><script>\u2028\u2029<!--"
    escaped = report._safe_js_json({"text": value, "zero": 0, "missing": None})
    assert json.loads(escaped) == {"text": value, "zero": 0, "missing": None}
    assert "<" not in escaped and "\u2028" not in escaped and "\u2029" not in escaped
    for number in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            report._safe_js_json({"number": number})
    with pytest.raises(ValueError, match="Restricted field"):
        report.render_html({"unexpected": "m32blind_n200_mixed_centre_loose_uniform-000"})
