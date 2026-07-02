"""
模块：TOCC（Trace-Conditioned Operator-Card Controller，基于运行轨迹的算子卡片控制器）
功能：作为 tocc 子包的统一入口，把分散在各子模块中的核心能力汇总成一套对外接口。
职责：集中导入并重新导出诊断、上下文策略、提案校验、执行流水线与迭代循环这几类公共符号，供外部按名引用。
接口：
    - diagnose / TOCCDecision：根据运行轨迹做出诊断并给出决策结果对象。
    - LEGACY_TOCC_SELECTED_CARDS_STRATEGY / TOCC_CANDIDATE_POOL_STRATEGY / normalize_tocc_context_strategy：上下文策略常量与归一化函数。
    - validate_proposal：对候选提案做合法性校验（守门）。
    - run_tocc_v2_cycle：执行一轮 TOCC 处理流程。
    - run_v3_loop：驱动多轮迭代循环。
输入：无独立输入；依赖同一子包下的 controller / contracts / gatekeeper / pipeline / loop 模块。
输出：通过 __all__ 暴露上述公共名称，构成本子包的对外 API。
"""

# 从各子模块导入并集中重新导出，构成 tocc 子包的公共接口。
# 诊断入口与决策结果类型
from .controller import diagnose, TOCCDecision
# 上下文策略相关：两个策略常量与一个策略名归一化函数
from .contracts import (
    LEGACY_TOCC_SELECTED_CARDS_STRATEGY,
    TOCC_CANDIDATE_POOL_STRATEGY,
    normalize_tocc_context_strategy,
)
# 提案守门：校验候选提案是否合法
from .gatekeeper import validate_proposal
# 单轮处理流程入口
from .pipeline import run_tocc_v2_cycle
# 多轮迭代循环入口
from .loop import run_v3_loop

# 显式声明对外暴露的公共名称，约束 `from tocc import *` 的导出范围
__all__ = [
    "diagnose",
    "LEGACY_TOCC_SELECTED_CARDS_STRATEGY",
    "TOCC_CANDIDATE_POOL_STRATEGY",
    "TOCCDecision",
    "normalize_tocc_context_strategy",
    "validate_proposal",
    "run_tocc_v2_cycle",
    "run_v3_loop",
]
