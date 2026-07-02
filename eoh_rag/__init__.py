"""EOH experiment framework — Trace-Conditioned Small-Model Controller.

Modules:
- eoh_rag.experiments: batch_runner, eoh_single_runner, rag_context_builder
- eoh_rag.rag: retriever, reranker, llm_reranker, card_outcomes, features
- eoh_rag.tocc: agent, gatekeeper, pipeline, controller
- eoh_rag.llm: client
"""

from .memory import read_text_file, write_text_file, append_research_note

__all__ = [
    "read_text_file",
    "write_text_file",
    "append_research_note",
]
