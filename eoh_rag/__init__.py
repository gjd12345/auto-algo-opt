"""
模块：eoh_rag
功能：EOH 实验框架的包入口，用 LLM 驱动地演化组合优化问题（在线装箱、TSP、CVRP、InsertShips）的启发式算法。
职责：聚合各子模块，并把最常用的文本读写工具函数提升到包顶层，方便直接从 eoh_rag 导入。
接口：read_text_file / write_text_file / append_research_note 三个文本工具函数（均从 .memory 转发）。
输入：无需环境变量；子模块按各自需要读取文件与参数。
输出：一个可导入的 Python 包，暴露 __all__ 中列出的公开名称。

子模块概览：
- eoh_rag.experiments：batch_runner、eoh_single_runner、rag_context_builder（实验批量与单次运行、检索上下文构建）
- eoh_rag.rag：retriever、reranker、llm_reranker、card_outcomes、features（检索、重排、LLM 重排、卡片效果、特征）
- eoh_rag.tocc：agent、gatekeeper、pipeline、controller（智能体、门控、流水线、控制器）
- eoh_rag.llm：client（大模型调用客户端）
"""

# 从 memory 子模块转发常用文本工具，使调用方可直接 `from eoh_rag import read_text_file` 等
from .memory import read_text_file, write_text_file, append_research_note

# 声明包对外公开的名称，控制 `from eoh_rag import *` 的导出范围
__all__ = [
    "read_text_file",
    "write_text_file",
    "append_research_note",
]
