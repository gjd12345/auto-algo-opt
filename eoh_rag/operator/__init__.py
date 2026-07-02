"""
模块：eoh_rag.operator
功能：把「进化算子」相关的能力集中成一个包，对外统一暴露入口。
职责：汇总并转发各子模块的公开类/函数，让调用方从本包一处导入，无需关心内部文件划分。
接口（转发自各子模块）：
  - repair_compile_errors：借助 LLM 自动修复候选启发式的编译错误。
  - FailureMemory：记录并复用历史失败样本，避免重复踩坑。
  - DirectedMutator：在给定方向/意图下对启发式代码做定向变异。
  - BoundedReactPlanner / StrategySpec / render_strategy：受约束的策略规划、策略规格数据结构、把规格渲染成可执行代码。
  - SmartOperator：整合上述能力的智能算子入口。
输入：无（纯 re-export；实际依赖由各子模块自行声明）。
输出：本包命名空间下的上述公开符号（见 __all__）。
"""

# 从各子模块导入公开符号，集中在本包命名空间对外提供
from .self_repair import repair_compile_errors
from .failure_memory import FailureMemory
from .directed_mutate import DirectedMutator
from .strategy_templates import BoundedReactPlanner, StrategySpec, render_strategy
from .agent_controller import SmartOperator

# __all__ 声明 `from eoh_rag.operator import *` 时导出的公开接口范围
__all__ = [
    "repair_compile_errors",
    "FailureMemory",
    "DirectedMutator",
    "BoundedReactPlanner",
    "StrategySpec",
    "render_strategy",
    "SmartOperator",
]
