"""
模块：rag（轻量级检索增强工具包）
功能：为 InsertShips 启发式提示词构建检索上下文，把语料库检索、特征抽取、重排与上下文拼装的能力统一对外暴露。
职责：作为本子包的统一入口，从各内部模块汇聚公开接口，供上层提示词流程按名字导入使用。
接口：检索类 retrieve / retrieve_with_rerank / RerankConfig；特征类 extract_*_features、load_population_features、normalize_strategy_feature、STRATEGY_FEATURES；语料类 CorpusItem / load_corpus / save_corpus；上下文类 format_prompt_context / format_prompt_context_with_audit。
输出：一组可直接 `from rag import ...` 使用的函数、类与常量（见 __all__）。
"""

# 提示词上下文拼装：把检索到的语料格式化为可注入提示词的文本（后者附带审计信息）
from .prompt_context import format_prompt_context, format_prompt_context_with_audit
# 特征抽取：从卡片/代码/策略中提取特征，用于检索与重排的相似度计算
from .features import (
    STRATEGY_FEATURES,
    extract_card_features,
    extract_code_features,
    extract_identifier_tokens,
    extract_strategy_features,
    load_population_features,
    normalize_strategy_feature,
)
# 重排：在初步召回结果之上做二次排序，RerankConfig 承载重排参数
from .reranker import RerankConfig, retrieve_with_rerank
# 检索：从语料库中召回与当前查询相关的条目
from .retriever import (
    retrieve,
)
# 语料结构与读写：CorpusItem 为单条语料，load/save 负责语料库的加载与持久化
from .schemas import CorpusItem, load_corpus, save_corpus

# __all__ 声明本子包对外公开的名字，`from rag import *` 时仅导出以下成员

__all__ = [
    "CorpusItem",
    "RerankConfig",
    "STRATEGY_FEATURES",
    "extract_card_features",
    "extract_code_features",
    "extract_identifier_tokens",
    "extract_strategy_features",
    "format_prompt_context",
    "format_prompt_context_with_audit",
    "load_corpus",
    "load_population_features",
    "normalize_strategy_feature",
    "retrieve",
    "retrieve_with_rerank",
    "save_corpus",
]
