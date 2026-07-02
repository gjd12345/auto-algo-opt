"""
模块：memory（文本记忆读写工具）
功能：为启发式进化框架提供纯文本文件的读取、写入与研究笔记追加能力，作为轻量的“记忆层”存取工具。
职责：统一处理 UTF-8 文本文件的读写，自动创建缺失的父目录，并以带时间戳的分块格式累积研究笔记。
接口：
    - read_text_file(path: Path) -> str：读取文本，文件不存在时返回空串。
    - write_text_file(path: Path, content: str) -> None：整体覆盖写入文本。
    - append_research_note(path: Path, title: str, content: str) -> None：向笔记文件追加一段带标题和时间戳的内容。
输入：调用方传入的目标文件路径（pathlib.Path）与待写入的字符串内容。
输出：磁盘上的 UTF-8 文本文件（读取时返回字符串，写入/追加时无返回值）。
示例：
    write_text_file(Path("out/best.txt"), "some heuristic code")
    append_research_note(Path("out/notes.md"), "TSP 观察", "该策略在小规模实例上收敛更快")
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path


def read_text_file(path: Path) -> str:
    """读取指定路径的 UTF-8 文本文件。

    参数：
        path：目标文件路径。
    返回：
        文件内容字符串；若文件不存在则返回空字符串（不抛异常，便于调用方安全兜底）。
    """
    # 文件不存在时返回空串，让调用方无需自行处理缺失情况
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_text_file(path: Path, content: str) -> None:
    """以 UTF-8 编码将内容整体写入文件（存在则覆盖）。

    参数：
        path：目标文件路径。
        content：要写入的完整文本内容。
    """
    # 自动补齐缺失的父级目录，避免因目录不存在而写入失败
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def append_research_note(path: Path, title: str, content: str) -> None:
    """向研究笔记文件追加一段带标题与时间戳的记录。

    每条笔记以 Markdown 二级标题呈现，并附加当前时间戳；多条笔记之间用分隔线隔开，
    从而在同一文件中按时间顺序累积多次观察结果。

    参数：
        path：笔记文件路径。
        title：本段笔记的标题。
        content：本段笔记的正文（首尾空白会被去除）。
    """
    # 确保笔记文件所在目录存在
    path.parent.mkdir(parents=True, exist_ok=True)
    # 记录写入时刻，便于回溯每条笔记的产生时间
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 组装单段笔记：标题 + 时间戳 + 正文
    block = f"\n## {title}\n*Timestamp: {timestamp}*\n\n{content.strip()}\n"
    # 读取已有内容以便在其后追加；文件不存在时视为空
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    # 仅当文件已有实际内容时才插入分隔线，避免文件开头出现多余的分隔符
    separator = "\n---\n" if existing.strip() else ""
    path.write_text(existing + separator + block, encoding="utf-8")
