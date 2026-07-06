"""守卫 m3 算子 prompt 与 EoH 输出契约对齐。

m3(去过拟合算子)曾因缺少"描述放花括号 + 函数签名(spec)"契约而 0 产出、白吞进化预算;
本测试防止回退。按源码切片检查,避免在 3.9 下导入需 3.10 语法的引擎主体。
"""
from __future__ import annotations

from pathlib import Path

_SRC = (
    Path(__file__).resolve().parents[1]
    / "official_eoh" / "eoh" / "src" / "eoh" / "eoh" / "evolution.py"
).read_text(encoding="utf-8")


def _m3_block() -> str:
    start = _SRC.index('if operator == "m3":')
    end = _SRC.index('raise ValueError(f"Unknown operator', start)
    return _SRC[start:end]


def test_m3_requests_braced_description():
    # 与 e1/e2/m1/m2 一致:要求把算法描述放进花括号,供 _extract 抽取。
    assert "inside a brace" in _m3_block()


def test_m3_uses_func_spec():
    # 复用统一的函数签名契约(spec),使输出为可解析的完整函数。
    assert "{spec}" in _m3_block()


def test_m3_keeps_deoverfit_intent():
    block = _m3_block()
    assert "overfit" in block and "generaliz" in block
