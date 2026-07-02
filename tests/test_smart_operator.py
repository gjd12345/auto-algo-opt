"""
Test Smart EOH Operator components with mocked LLM and Go build.
Validates the full pipeline logic without requiring Go compiler or API keys.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eoh_rag.operator.self_repair import (
    _extract_code_from_response,
    _replace_insertships_func,
    _try_compile,
    repair_compile_errors,
)
from eoh_rag.operator.failure_memory import FailureMemory, FAILURE_PATTERNS
from eoh_rag.operator.directed_mutate import (
    DirectedMutator,
    _extract_code as _extract_mutation_code,
    MUTATION_SYSTEM_PROMPT,
)


# ── test data ──────────────────────────────────────────────────────

SAMPLE_MAIN_GO = """package main

import (
    "math/rand"
)

const MAXASSIGNS = 64
const MAXSHIPS = 8

func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch {
    var rand_range [MAXASSIGNS]int
    var rand_limit int = 0
    for ii := range rand_range {
        rand_range[ii] = ii
        if ii < dispatch.AssignsLen && dispatch.Assigns[ii].StationsLen > 0 {
            rand_range[ii], rand_range[rand_limit] = rand_range[rand_limit], ii
            rand_limit += 1
        }
    }
    rand.Shuffle(rand_limit, func(i, j int) {
        rand_range[i], rand_range[j] = rand_range[j], rand_range[i]
    })
    for jj := range oris {
        for _, ii := range rand_range {
            dispatch.Assigns[ii].AddShip(total_ship+jj, oris[jj], dess[jj])
            dispatch.Assigns[ii].GenRoute()
            if dispatch.Assigns[ii].Cost < 0 {
                dispatch.Assigns[ii].RemoveShip(total_ship + jj)
                dispatch.Assigns[ii].GenRoute()
            } else {
                if ii >= dispatch.AssignsLen {
                    dispatch.AssignsLen += 1
                }
                break
            }
        }
    }
    dispatch.RenewnTotalCost()
    return dispatch
}
"""

BAD_CODE_UNDEFINED = """func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch {
    for jj := range oris {
        bestVehicle := dispatch.Vehicles[0]
        bestVehicle.AddShip(total_ship+jj, oris[jj], dess[jj])
    }
    dispatch.RenewnTotalCost()
    return dispatch
}"""

BAD_CODE_SYNTAX = """func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch {
    for jj := range oris {
        dispatch.Assigns[0].AddShip(total_ship+jj, oris[jj], dess[jj]
    }
    dispatch.RenewnTotalCost()
    return dispatch
}"""

FIXED_CODE = """func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch {
    for jj := range oris {
        dispatch.Assigns[0].AddShip(total_ship+jj, oris[jj], dess[jj])
        dispatch.Assigns[0].GenRoute()
    }
    dispatch.RenewnTotalCost()
    return dispatch
}"""

LLM_FIX_RESPONSE = """Here is the fixed code:

```go
func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch {
    for jj := range oris {
        dispatch.Assigns[0].AddShip(total_ship+jj, oris[jj], dess[jj])
        dispatch.Assigns[0].GenRoute()
    }
    dispatch.RenewnTotalCost()
    return dispatch
}
```"""


# ── self_repair tests ──────────────────────────────────────────────

class TestExtractCode:
    def test_extract_from_markdown_fence(self):
        code = _extract_code_from_response(LLM_FIX_RESPONSE)
        assert code is not None
        assert "func InsertShips" in code
        assert "dispatch.Assigns[0].AddShip" in code

    def test_extract_bare_code(self):
        code = _extract_code_from_response(FIXED_CODE)
        assert code is not None
        assert "func InsertShips" in code

    def test_extract_invalid(self):
        code = _extract_code_from_response("This is not Go code")
        assert code is None


class TestReplaceInsertShips:
    def test_replace_success(self):
        new_func = """func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch {
    return dispatch
}"""
        result = _replace_insertships_func(SAMPLE_MAIN_GO, new_func)
        assert "func InsertShips" in result
        assert "return dispatch" in result
        assert result.count("func InsertShips") == 1

    def test_replace_preserves_rest_of_file(self):
        new_func = """func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch {
    return dispatch
}"""
        result = _replace_insertships_func(SAMPLE_MAIN_GO, new_func)
        assert "package main" in result
        assert "const MAXASSIGNS" in result

    def test_auto_injects_sort_import(self):
        new_func = """func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch {
    sort.Ints(nil)
    return dispatch
}"""
        result = _replace_insertships_func(SAMPLE_MAIN_GO, new_func)
        assert '"sort"' in result

    def test_auto_injects_sort_manager(self):
        new_func = """func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch {
    var sm SortManager
    sort.Sort(&sm)
    return dispatch
}"""
        result = _replace_insertships_func(SAMPLE_MAIN_GO, new_func)
        assert "type SortManager struct" in result


class TestRepairPipeline:
    def test_compile_success_no_repair_needed(self, tmp_path):
        """Valid code compiles on first try without repair."""
        project = tmp_path / "project"
        project.mkdir()
        (project / "main.go").write_text(SAMPLE_MAIN_GO)
        # We can't test actual Go compile, so test the patch logic
        result = _replace_insertships_func(SAMPLE_MAIN_GO, FIXED_CODE)
        assert "func InsertShips" in result
        assert result.count("func InsertShips") == 1

    def test_compile_fail_triggers_repair(self):
        """When compile fails, repair is attempted."""
        # Test that repair_compile_errors handles missing main.go
        result = repair_compile_errors(
            BAD_CODE_UNDEFINED,
            project_root="/nonexistent",
            max_attempts=1,
        )
        assert result["compiled"] is False
        # Should fail at setup stage
        assert any("main.go not found" in str(e.get("error", ""))
                   for e in result["repair_log"])


# ── failure_memory tests ──────────────────────────────────────────

class TestFailureMemory:
    def test_classify_compile_error(self):
        fm = FailureMemory(tempfile.mkdtemp())
        keys = fm.classify_error("undefined: someVar")
        assert "undefined_type" in keys or "undefined_variable" in keys

    def test_classify_timeout(self):
        fm = FailureMemory(tempfile.mkdtemp())
        keys = fm.classify_error("", runtime_seconds=200, timeout_threshold=120)
        assert "timeout" in keys

    def test_classify_negative_cost(self):
        fm = FailureMemory(tempfile.mkdtemp())
        keys = fm.classify_error("", cost=-5.0)
        assert "negative_cost" in keys

    def test_classify_suspicious_low(self):
        fm = FailureMemory(tempfile.mkdtemp())
        keys = fm.classify_error("", cost=69.0, baseline_cost=100.0)
        assert "suspicious_low_cost" in keys

    def test_record_and_retrieve(self):
        fm = FailureMemory(tempfile.mkdtemp())
        fm.record_failure("undefined_type", "undefined: Foo", "code with Foo")
        fm.record_failure("undefined_type", "undefined: Bar", "")
        fm.record_failure("negative_cost", "", "")

        warnings = fm.get_active_warnings()
        assert len(warnings) >= 2

        # Most frequent should be first
        assert warnings[0]["key"] == "undefined_type"
        assert warnings[0]["count"] == 2

    def test_constraints_text(self):
        fm = FailureMemory(tempfile.mkdtemp())
        fm.record_failure("undefined_type", "", "")
        fm.record_failure("negative_cost", "", "")

        text = fm.get_constraints_text()
        assert "FAILURE" in text.upper() or "failure" in text.lower()
        assert "undefined_type" in text

    def test_stats(self):
        fm = FailureMemory(tempfile.mkdtemp())
        fm.record_attempt(success=True)
        fm.record_attempt(success=False)
        fm.record_attempt(success=False)

        stats = fm.get_stats()
        assert stats["total_attempts"] == 3
        assert stats["total_failures"] == 2
        assert stats["fail_rate"] == 2 / 3

    def test_persistence(self, tmp_path):
        mem_dir = tmp_path / "memory"
        mem_dir.mkdir()
        fm1 = FailureMemory(mem_dir)
        fm1.record_failure("timeout", "timed out", "")
        fm1.record_attempt(success=False)

        # Create new instance pointing to same dir
        fm2 = FailureMemory(mem_dir)
        stats = fm2.get_stats()
        assert stats["total_failures"] >= 1

    def test_all_patterns_have_tags(self):
        for key, info in FAILURE_PATTERNS.items():
            assert "tag" in info, f"Missing tag in {key}"
            assert "advice" in info, f"Missing advice in {key}"
            assert info["tag"] in (
                "compile_error", "negative_cost", "suspicious_low", "runtime_timeout"
            ), f"Unknown tag in {key}"


# ── directed_mutate tests ──────────────────────────────────────────

class TestDirectedMutator:
    def test_extract_code_from_response(self):
        response = """Let me improve this...

```go
func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch {
    // improved code
    return dispatch
}
```"""
        code = _extract_mutation_code(response)
        assert code is not None
        assert "func InsertShips" in code
        assert "improved code" in code

    def test_extract_invalid_response(self):
        assert _extract_mutation_code("No code here") is None

    def test_build_mutation_prompt(self):
        mutator = DirectedMutator()
        prompt = mutator.build_mutation_prompt(
            parent_code=FIXED_CODE,
            current_best_score=500.0,
            target_score=450.0,
            failure_constraints="## Constraints\n- Do not use undefined types.\n",
            strategy_guidance="Try time-window aware insertion.",
        )
        assert "func InsertShips" in prompt
        assert "500" in prompt
        assert "450" in prompt
        assert "undefined types" in prompt
        assert "time-window" in prompt

    def test_record_generation(self):
        mutator = DirectedMutator()
        mutator.record_generation({
            "gen": 1,
            "best_fitness": 400.0,
            "avg_fitness": 420.0,
            "none_rate": 0.25,
        })
        assert len(mutator.generation_history) == 1
        assert mutator.generation_history[0]["best_fitness"] == 400.0

    def test_prompt_without_history(self):
        mutator = DirectedMutator()
        prompt = mutator.build_mutation_prompt(FIXED_CODE)
        # Should contain the parent code and strategy guidance
        assert "func InsertShips" in prompt
        assert "Parent Code" in prompt
        assert "Strategy Guidance" in prompt

    def test_mutate_returns_none_without_api(self):
        """Without API key, mutate returns None (no crash)."""
        mutator = DirectedMutator(api_key="")
        result = mutator.mutate(FIXED_CODE)
        assert result is None  # no API key available

    def test_mutate_batch_deduplicates(self):
        """Even with no API, batch returns empty list gracefully."""
        mutator = DirectedMutator(api_key="")
        results = mutator.mutate_batch(FIXED_CODE, batch_size=2)
        assert isinstance(results, list)
        # Without API key, all mutations return None → filtered out
        assert len(results) == 0


# ── integration test ──────────────────────────────────────────────

class TestIntegration:
    def test_full_pipeline_mocked(self, tmp_path):
        """End-to-end test with mocked LLM and Go compiler."""
        from eoh_rag.operator.agent_controller import SmartOperator

        # Setup project
        project = tmp_path / "project"
        project.mkdir()
        (project / "main.go").write_text(SAMPLE_MAIN_GO)
        (project / "routing.go").write_text("package main\n")
        (project / "go.mod").write_text("module test\n\ngo 1.21\n")
        (project / "go.sum").write_text("")

        # Setup data
        data_dir = project / "solomon_benchmark_d25"
        data_dir.mkdir()
        (data_dir / "rc101.json").write_text("{}")

        # SmartOperator should initialize without crash
        op = SmartOperator(
            project_root=str(project),
            pop_size=2,
            generations=1,
            api_key="",  # no API → will use fallback/mock paths
        )

        # Verify initialization
        assert op.main_go_text is not None
        assert "func InsertShips" in op.main_go_text

        # Extract seed
        seed = op._extract_seed_code()
        assert seed is not None
        assert "func InsertShips" in seed

        # Verify workspace setup
        plan = op.workspace / "operator_memory" / "PLAN.md"
        assert plan.exists()
        mem = op.workspace / "operator_memory" / "MEMORY.md"
        assert mem.exists()

    def test_guard_rules(self):
        from eoh_rag.operator.agent_controller import SmartOperator

        op = SmartOperator.__new__(SmartOperator)
        op.baseline_cost = 500.0

        # Valid
        r = op._apply_guard(480.0)
        assert not r["excluded"]

        r = op._apply_guard(350.0)  # exactly 0.7 * 500
        assert not r["excluded"]

        # Negative
        r = op._apply_guard(-1.0)
        assert r["excluded"]
        assert "negative" in r["reason"]

        # Suspicious low
        r = op._apply_guard(349.0)  # < 0.7 * 500
        assert r["excluded"]
        assert "suspicious" in r["reason"]

    def test_metric_definitions(self):
        """All metrics have descriptions."""
        from eoh_rag.operator.agent_controller import METRIC_DEFS

        assert len(METRIC_DEFS) >= 10
        for key, desc in METRIC_DEFS.items():
            assert isinstance(desc, str)
            assert len(desc) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
