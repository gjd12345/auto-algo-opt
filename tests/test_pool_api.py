"""
脚本：test_pool_api.py
功能：覆盖 PoolAPI 的 4 类 pool 读写路径 —— run 索引 / 精英代码 / 算子统计 / 失败模式。
输入：无（用 tmp_path fixture 隔离）
输出：pytest 断言
用法：pytest tests/test_pool_api.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eoh_rag.experiments.pool_api import PoolAPI


# --------------------------------------------------------------------------- #
# run 索引                                                                     #
# --------------------------------------------------------------------------- #


def test_register_and_best_run(tmp_path: Path) -> None:
    pool = PoolAPI(tmp_path)
    pool.register_run("bp_online", "/runs/a", 0.05)
    pool.register_run("bp_online", "/runs/b", 0.03)  # 更好
    pool.register_run("bp_online", "/runs/c", 0.04)
    assert pool.best_run("bp_online") == "/runs/b"


def test_best_run_isolates_per_problem(tmp_path: Path) -> None:
    pool = PoolAPI(tmp_path)
    pool.register_run("bp_online", "/runs/bp", 0.02)
    pool.register_run("tsp_construct", "/runs/tsp", 6.5)
    assert pool.best_run("bp_online") == "/runs/bp"
    assert pool.best_run("tsp_construct") == "/runs/tsp"
    assert pool.best_run("cvrp_construct") == ""


def test_list_runs_filter(tmp_path: Path) -> None:
    pool = PoolAPI(tmp_path)
    pool.register_run("bp_online", "/a", 0.05)
    pool.register_run("tsp_construct", "/b", 6.5)
    assert len(pool.list_runs()) == 2
    assert len(pool.list_runs("bp_online")) == 1


def test_register_run_extra_meta(tmp_path: Path) -> None:
    pool = PoolAPI(tmp_path)
    pool.register_run("bp_online", "/a", 0.05, seed=42, commit="abc")
    entry = pool.list_runs("bp_online")[0]
    assert entry["seed"] == 42
    assert entry["commit"] == "abc"


def test_best_run_empty(tmp_path: Path) -> None:
    assert PoolAPI(tmp_path).best_run("bp_online") == ""


# --------------------------------------------------------------------------- #
# 精英代码                                                                     #
# --------------------------------------------------------------------------- #


def test_best_codes_top_k_and_dedup(tmp_path: Path) -> None:
    pool = PoolAPI(tmp_path)
    pool.register_code("bp_online", "code_A", 0.03)
    pool.register_code("bp_online", "code_A", 0.03)  # 完全相同的代码：按代码内容去重
    pool.register_code("bp_online", "code_E", 0.03)  # 目标值相同但代码不同：保留以保多样性
    pool.register_code("bp_online", "code_B", 0.04)
    pool.register_code("bp_online", "code_C", 0.05)
    result = pool.best_codes("bp_online", top_k=3)
    assert len(result) == 3
    # code_A 与 code_E 目标值都是 0.03、但结构不同，都应保留
    assert [r["objective"] for r in result] == [0.03, 0.03, 0.04]
    assert {r["code"] for r in result} == {"code_A", "code_E", "code_B"}


def test_best_codes_empty(tmp_path: Path) -> None:
    assert PoolAPI(tmp_path).best_codes("bp_online") == []


def test_snapshot_is_stable_problem_isolated_and_read_only(tmp_path: Path) -> None:
    pool = PoolAPI(tmp_path)
    pool.register_code("bp_online", "x = 1", 2.0, ts=3.0)
    pool.register_code("bp_online", "x = 2", 1.0, ts=2.0)
    pool.register_code("tsp_construct", "x = 9", 0.1, ts=1.0)
    before = sorted(path.name for path in tmp_path.iterdir())
    rows = pool.snapshot("bp_online", top_k=2)
    rows[0]["code"] = "mutated"
    assert [row["objective"] for row in pool.snapshot("bp_online", top_k=2)] == [1.0, 2.0]
    assert all("x = 9" != row["code"] for row in rows)
    assert sorted(path.name for path in tmp_path.iterdir()) == before


# --------------------------------------------------------------------------- #
# 算子成功率                                                                   #
# --------------------------------------------------------------------------- #


def test_operator_weights_below_threshold(tmp_path: Path) -> None:
    """总样本 < 3 时权重恒为 1.0。"""
    pool = PoolAPI(tmp_path)
    pool.register_operator_stat("bp_online", "e1", True, 0.01)
    pool.register_operator_stat("bp_online", "e1", True, 0.02)
    weights = pool.operator_weights("bp_online")
    assert weights["e1"] == pytest.approx(1.0)


def test_operator_weights_full_success(tmp_path: Path) -> None:
    """总样本 >= 3 且全成功 → 权重 = 0.5 + 1.0 = 1.5。"""
    pool = PoolAPI(tmp_path)
    for _ in range(3):
        pool.register_operator_stat("bp_online", "m1", True, 0.01)
    weights = pool.operator_weights("bp_online")
    assert weights["m1"] == pytest.approx(1.5)


def test_operator_weights_mixed(tmp_path: Path) -> None:
    """success_rate = 2/4 = 0.5 → weight = 1.0。"""
    pool = PoolAPI(tmp_path)
    for improved in [True, True, False, False]:
        pool.register_operator_stat("bp_online", "e2", improved, 0.0)
    weights = pool.operator_weights("bp_online")
    assert weights["e2"] == pytest.approx(1.0)


def test_operator_weights_empty(tmp_path: Path) -> None:
    assert PoolAPI(tmp_path).operator_weights("bp_online") == {}


# --------------------------------------------------------------------------- #
# 失败模式                                                                     #
# --------------------------------------------------------------------------- #


def test_failure_hints_frequency_order(tmp_path: Path) -> None:
    pool = PoolAPI(tmp_path)
    pool.register_failure("bp_online", "return None", "invalid_output")
    pool.register_failure("bp_online", "return None", "invalid_output")
    pool.register_failure("bp_online", "x / 0", "runtime_error")
    hints = pool.failure_hints("bp_online", top_k=2)
    assert hints[0].startswith("MUST return valid output")
    assert len(hints) == 2


def test_failure_hints_explicit_pattern(tmp_path: Path) -> None:
    pool = PoolAPI(tmp_path)
    pool.register_failure("bp_online", "code", "runtime_error", pattern_hint="custom hint")
    assert pool.failure_hints("bp_online") == ["custom hint"]


def test_failure_hints_static_extractor(tmp_path: Path) -> None:
    """未提供 pattern_hint 时使用静态规则推断。"""
    pool = PoolAPI(tmp_path)
    pool.register_failure(
        "bp_online",
        "for i in items:\n    for j in items:\n        pass",
        "eval_timeout",
    )
    hints = pool.failure_hints("bp_online")
    assert "nested loops" in hints[0]


def test_failure_hints_empty(tmp_path: Path) -> None:
    assert PoolAPI(tmp_path).failure_hints("bp_online") == []


# --------------------------------------------------------------------------- #
# 目录 & 并发                                                                  #
# --------------------------------------------------------------------------- #


def test_pool_dir_lazy_create(tmp_path: Path) -> None:
    """PoolAPI 不该在构造时就 mkdir，只在首次写入时创建。"""
    target = tmp_path / "not_yet"
    pool = PoolAPI(target)
    assert not target.exists()
    pool.register_run("bp_online", "/a", 0.05)
    assert target.exists()


def test_read_ignores_blank_lines(tmp_path: Path) -> None:
    """手工在 JSONL 结尾留了空行时不应崩。"""
    pool = PoolAPI(tmp_path)
    pool.register_run("bp_online", "/a", 0.05)
    idx = tmp_path / "pool_index.jsonl"
    idx.write_text(idx.read_text() + "\n\n")
    assert pool.best_run("bp_online") == "/a"
