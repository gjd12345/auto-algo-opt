"""
模块：TOCC 清单契约（contracts）
功能：为 TOCC 实验清单（manifest）中的“上下文策略”字段提供稳定的取值常量，并把等价的别名统一成规范名。
职责：
    - 集中定义 context_strategy 字段的规范取值，避免各处硬编码字符串导致不一致。
    - 提供一个归一化函数，把已知的别名折叠成规范名，同时原样放行其它无关取值。
接口：
    - TOCC_CANDIDATE_POOL_STRATEGY：规范取值 "tocc_candidate_pool"（候选卡片池策略）。
    - LEGACY_TOCC_SELECTED_CARDS_STRATEGY：等价别名 "tocc_selected_cards"，会被归一化到规范取值。
    - normalize_tocc_context_strategy(value: str | None) -> str：把别名归一为规范名。
输入：来自实验清单每个 arm 的 context_strategy 字段（可能为 None 或任意字符串）。
输出：一个可安全比较的策略名字符串；已知别名统一为规范名，其它取值保持不变。
示例：
    >>> normalize_tocc_context_strategy("tocc_selected_cards")
    'tocc_candidate_pool'
    >>> normalize_tocc_context_strategy("manual_context")
    'manual_context'
"""
from __future__ import annotations


# 规范取值：候选卡片池策略。gatekeeper / loop 写入清单时统一使用这个常量，
# batch_runner 等下游读取 context_strategy 时以它为准。
TOCC_CANDIDATE_POOL_STRATEGY = "tocc_candidate_pool"
# 等价别名：语义与上面的规范取值一致，归一化时会被折叠成规范名。
LEGACY_TOCC_SELECTED_CARDS_STRATEGY = "tocc_selected_cards"


def normalize_tocc_context_strategy(value: str | None) -> str:
    """把上下文策略名归一化为规范取值。

    仅对已知别名做转换，其它取值一律原样返回，因此可以安全地用于任意 context_strategy 字段。

    参数：
        value：清单中的 context_strategy 原始值，允许为 None 或任意字符串。

    返回：
        规范化后的策略名字符串。若输入等于已知别名，则返回对应的规范取值；
        否则（包括 None、空串、无关模式名）返回其字符串形式，保持原意不变。
    """
    # 先统一成字符串：None 或空值转成空串，避免下游比较时出现类型问题。
    strategy = str(value or "")
    # 命中已知别名时折叠成规范取值；其余取值直接放行。
    if strategy == LEGACY_TOCC_SELECTED_CARDS_STRATEGY:
        return TOCC_CANDIDATE_POOL_STRATEGY
    return strategy
