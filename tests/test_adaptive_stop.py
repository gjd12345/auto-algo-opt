"""Tests _should_stop —— 自适应早停判据。

按文件路径直接加载 `_adaptive.py`,避免导入依赖 Python 3.10+ 的引擎主体,
使本测试在任意 Python 版本下都能运行。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_MOD = (
    Path(__file__).resolve().parents[1]
    / "official_eoh" / "eoh" / "src" / "eoh" / "eoh" / "_adaptive.py"
)
_spec = importlib.util.spec_from_file_location("_adaptive_under_test", _MOD)
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
_should_stop = _m._should_stop


def test_still_improving_continues():
    # 最近 5 代仍明显改进(约 25%),远超阈值 → 不停
    hist = [0.040, 0.038, 0.036, 0.034, 0.032, 0.030]
    assert _should_stop(hist, 5, 0.01) is False


def test_plateau_stops():
    # 最近 5 代相对改进 < 1% → 停
    hist = [0.006900, 0.006899, 0.006898, 0.006897, 0.006896, 0.006895]
    assert _should_stop(hist, 5, 0.01) is True


def test_insufficient_history_continues():
    assert _should_stop([0.04, 0.03, 0.02], 5, 0.01) is False  # 点数 <= window
    assert _should_stop([], 5, 0.01) is False


def test_none_or_nonpositive_endpoints_continue():
    assert _should_stop([None, 0.03, 0.028, 0.027, 0.026, 0.0255], 5, 0.01) is False
    assert _should_stop([0.0, 0.0, 0.0, 0.0, 0.0, 0.0], 5, 0.01) is False  # prev<=0


def test_threshold_boundary():
    # gap 恰等于阈值不算低于(判据用 <,非 <=)→ 继续;阈值略大才停。
    # 用可精确表示的值(1.0→0.5,gap=0.5)避免浮点边界误差。
    hist = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]  # gap = (1.0-0.5)/1.0 = 0.5
    assert _should_stop(hist, 5, 0.5) is False
    assert _should_stop(hist, 5, 0.6) is True


def test_window_uses_last_w_gens_only():
    # 早期大幅改进,但最近 5 代已平台 → 应停(判据只看最近 window 代)
    hist = [0.5, 0.1, 0.05, 0.0500, 0.04999, 0.04998, 0.04997, 0.04996, 0.04995, 0.04994]
    assert _should_stop(hist, 5, 0.01) is True
