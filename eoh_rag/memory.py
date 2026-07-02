from __future__ import annotations

from datetime import datetime
from pathlib import Path


def read_text_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def append_research_note(path: Path, title: str, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    block = f"\n## {title}\n*Timestamp: {timestamp}*\n\n{content.strip()}\n"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    separator = "\n---\n" if existing.strip() else ""
    path.write_text(existing + separator + block, encoding="utf-8")
