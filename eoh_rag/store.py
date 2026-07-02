"""
模块：eoh_rag.store
功能：提供一组读写 JSON 文件的轻量工具函数，供 RAG 检索模块持久化数据使用。
职责：负责本地 JSON 文件的读取、整体写入，以及向 JSON 列表文件追加单条记录。
接口：
    - read_json(path, default)：读文件；文件不存在时返回默认值。
    - write_json(path, data)：把数据以 JSON 格式写入文件（自动创建父目录）。
    - append_json_list(path, item)：把一条记录追加到 JSON 列表文件末尾。
输入：文件路径（pathlib.Path）与要读写的 Python 数据对象。
输出：从磁盘反序列化得到的 Python 对象，或写入磁盘的 UTF-8 编码 JSON 文件。
示例：
    write_json(Path("data.json"), {"a": 1})
    data = read_json(Path("data.json"), default={})
    append_json_list(Path("log.json"), {"event": "run"})
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path, default: Any):
    """读取 JSON 文件并反序列化为 Python 对象。

    参数：
        path：待读取文件的路径。
        default：当文件不存在时返回的默认值（例如空列表或空字典）。
    返回：
        文件存在时返回解析后的 Python 对象；否则返回 default。
    """
    # 文件不存在则直接返回调用方给定的默认值，避免抛出异常。
    if not path.exists():
        return default
    # 以 UTF-8 编码读取文本内容并解析为 Python 对象。
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    """把 Python 对象序列化为 JSON 并写入文件。

    参数：
        path：目标文件路径；其父目录若不存在会被自动创建。
        data：要写入的 Python 数据对象。
    说明：
        使用 ensure_ascii=False 保留中文等非 ASCII 字符，indent=2 便于人工阅读。
    """
    # 确保父目录存在，parents/exist_ok 保证多级目录也能安全创建。
    path.parent.mkdir(parents=True, exist_ok=True)
    # 序列化后以 UTF-8 编码写入，保留原始字符并采用两空格缩进。
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_json_list(path: Path, item: Any) -> None:
    """向一个存放列表的 JSON 文件末尾追加一条记录。

    参数：
        path：存放列表的 JSON 文件路径。
        item：要追加的单条记录。
    说明：
        文件不存在时按空列表处理；若文件内容不是列表，则重置为一个空列表后再追加，
        以保证写回的结果始终是合法的 JSON 列表。
    """
    # 读取已有内容，文件不存在时默认视为空列表。
    data = read_json(path, [])
    # 若读到的内容不是列表（例如格式异常），则重置为空列表以保证结构正确。
    if not isinstance(data, list):
        data = []
    # 追加新记录后整体写回文件。
    data.append(item)
    write_json(path, data)
