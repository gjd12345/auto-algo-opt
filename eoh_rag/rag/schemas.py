"""
模块：schemas（RAG 语料的数据结构与读写）
功能：定义启发式检索增强（RAG）语料库中单条知识的结构，并提供 JSONL 文件的加载与保存能力。
职责：管理 CorpusItem 数据模型，负责语料在“Python 对象 <-> 字典 <-> JSONL 文本行”之间的相互转换。
接口：
    - CorpusItem：一条语料的不可变数据类（含 from_dict / to_dict 方法）。
    - load_corpus(path) -> list[CorpusItem]：从 JSONL 文件读出全部语料。
    - save_corpus(items, path) -> None：把语料逐行写入 JSONL 文件。
输入：一个 JSONL 语料文件路径（每行是一个 JSON 对象），或一批 CorpusItem 对象。
输出：内存中的 CorpusItem 列表，或写到磁盘上的 JSONL 语料文件。
示例：
    items = load_corpus("corpus.jsonl")   # 读出语料
    save_corpus(items, "corpus.jsonl")     # 再写回磁盘
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class CorpusItem:
    """RAG 语料库中的一条知识条目（不可变）。

    每个字段描述这条知识的一个方面，供检索和给大模型做上下文时使用：
        - id：条目唯一标识。
        - kind：条目类别（如算法思路、约束说明等）。
        - title：标题，便于人和检索快速识别。
        - tags：标签列表，用于按主题过滤或匹配。
        - source_path：原始来源路径，方便溯源。
        - summary：一句话摘要。
        - constraints：与该条目相关的约束条件列表。
        - content：正文，通常是最终提供给大模型的主体文本。

    使用 frozen=True 使实例不可修改，从而可安全地在多处共享。
    """

    id: str
    kind: str
    title: str
    tags: list[str]
    source_path: str
    summary: str
    constraints: list[str]
    content: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CorpusItem":
        """从字典构造 CorpusItem。

        对每个字段做类型规整：缺失字段用空字符串或空列表兜底，
        字符串字段统一转为 str，列表字段中的每个元素也转为 str，
        以保证读入的数据结构稳定、可预期。
        """
        return cls(
            id=str(payload.get("id", "")),
            kind=str(payload.get("kind", "")),
            title=str(payload.get("title", "")),
            tags=[str(item) for item in payload.get("tags", [])],
            source_path=str(payload.get("source_path", "")),
            summary=str(payload.get("summary", "")),
            constraints=[str(item) for item in payload.get("constraints", [])],
            content=str(payload.get("content", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        """把当前条目转成普通字典，便于序列化为 JSON。"""
        return asdict(self)


def load_corpus(path: str | Path) -> list[CorpusItem]:
    """从 JSONL 文件读取全部语料条目。

    文件每一行是一个 JSON 对象，对应一条 CorpusItem。空行会被跳过。
    当文件不存在或为空时返回空列表；当某行不是合法 JSON 或不是对象时，
    抛出 ValueError 并带上出错的文件名与行号，方便定位问题。

    参数 path：语料 JSONL 文件路径。
    返回：解析得到的 CorpusItem 列表。
    """
    corpus_path = Path(path)
    # 文件不存在或大小为 0 时，直接视为没有语料。
    if not corpus_path.exists() or corpus_path.stat().st_size == 0:
        return []

    items: list[CorpusItem] = []
    with corpus_path.open("r", encoding="utf-8") as handle:
        # 逐行读取，line_no 从 1 开始，用于错误提示中的行号。
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue  # 跳过空行
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                # 解析失败时保留原始异常链，并指明具体的文件位置。
                raise ValueError(f"Invalid JSONL at {corpus_path}:{line_no}") from exc
            # 每行必须是 JSON 对象（字典），否则无法映射到 CorpusItem。
            if not isinstance(payload, dict):
                raise ValueError(f"Corpus row must be an object at {corpus_path}:{line_no}")
            items.append(CorpusItem.from_dict(payload))
    return items


def save_corpus(items: Iterable[CorpusItem], path: str | Path) -> None:
    """把一批语料条目写入 JSONL 文件（每行一个 JSON 对象）。

    会自动创建目标文件所在的父目录。写出时 ensure_ascii=False 以保留中文，
    sort_keys=True 使字段顺序稳定、便于比对与版本管理。

    参数 items：待写出的 CorpusItem 可迭代对象。
    参数 path：目标 JSONL 文件路径（已存在则覆盖）。
    """
    corpus_path = Path(path)
    # 确保父目录存在，避免写文件时因目录缺失而报错。
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    with corpus_path.open("w", encoding="utf-8") as handle:
        for item in items:
            # 每条语料序列化为一行 JSON，再补一个换行符，构成 JSONL。
            handle.write(json.dumps(item.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write("\n")
