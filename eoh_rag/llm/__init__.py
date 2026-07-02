"""
模块：eoh_rag.llm
功能：汇总大语言模型（LLM）相关的公共接口，作为该子包的统一入口。
职责：对外暴露两个能力——调用 LLM 对话补全，以及从模型回复中抽取代码块。
接口：chat_completion（发起对话补全请求）、extract_code_block（解析回复中的代码块）。
"""

from .client import chat_completion
from .utils import extract_code_block

# __all__ 声明 from eoh_rag.llm import * 时对外可见的公共符号
__all__ = ["chat_completion", "extract_code_block"]
