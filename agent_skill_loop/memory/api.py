"""Small, model-free auto-memory backend.

The agent decides whether an observation is worth retaining.  This module only
validates the five-field frontmatter, stores Markdown atomically, and performs
bounded deterministic retrieval.  It never calls a model and never changes
workflow state.
"""

from __future__ import annotations

import os
import re
import tempfile
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
_FILE = re.compile(r"^(?P<type>insight|solution)_(?P<name>[A-Za-z0-9][A-Za-z0-9_-]{0,79}?)(?:__v(?P<version>[0-9]{4}))?\.md$")
_REFERENCE = re.compile(r"^(?P<project>[A-Za-z0-9_-]+|_shared)/(?:insight|solution)_[A-Za-z0-9][A-Za-z0-9_-]{0,79}@v(?P<version>[0-9]{4})$")
_SECRET = re.compile(r"(?i)(api[_-]?key|token|secret|password|access[_-]?token|bearer)\s*[:=]")
_FRONTMATTER = ("name", "description", "type", "project", "scene")


@dataclass(frozen=True)
class MemoryEntry:
    name: str
    description: str
    type: str
    project: str
    scene: str
    body: str

    def as_dict(self) -> dict[str, str]:
        return {
            "name": self.name, "description": self.description, "type": self.type,
            "project": self.project, "scene": self.scene, "body": self.body,
        }


def _validate_entry(entry: MemoryEntry) -> None:
    if not _NAME.fullmatch(entry.name):
        raise ValueError("memory_name_invalid")
    if entry.type not in {"insight", "solution"}:
        raise ValueError("memory_type_invalid")
    if not _NAME.fullmatch(entry.project) and entry.project != "_shared":
        raise ValueError("memory_project_invalid")
    if not entry.scene.strip() or len(entry.scene) > 128:
        raise ValueError("memory_scene_invalid")
    if not entry.description.strip() or len(entry.description) > 512:
        raise ValueError("memory_description_invalid")
    if not entry.body.strip() or len(entry.body.encode("utf-8")) > 20000:
        raise ValueError("memory_body_invalid")
    if _SECRET.search(entry.description) or _SECRET.search(entry.body):
        raise ValueError("memory_sensitive_value")
    if entry.type == "insight":
        if "**Why:**" not in entry.body or "**How to apply:**" not in entry.body:
            raise ValueError("insight_body_sections_missing")
    if entry.type == "solution" and "**Reusable Experience:**" not in entry.body:
        raise ValueError("solution_reusable_experience_missing")


def _yaml_value(value: str) -> str:
    if any(ch in value for ch in "\n\r"):
        raise ValueError("memory_frontmatter_multiline")
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _render(entry: MemoryEntry) -> str:
    return "---\n" + "".join(f'{key}: "{_yaml_value(getattr(entry, key))}"\n' for key in _FRONTMATTER) + "---\n\n" + entry.body.rstrip() + "\n"


def _parse(path: Path) -> MemoryEntry:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) < 8 or lines[0] != "---":
        raise ValueError("memory_frontmatter_missing")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise ValueError("memory_frontmatter_unclosed") from None
    values: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            raise ValueError("memory_frontmatter_invalid")
        key, value = line.split(":", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        values[key.strip()] = value
    if set(values) != set(_FRONTMATTER):
        raise ValueError("memory_frontmatter_fields_invalid")
    entry = MemoryEntry(**values, body="\n".join(lines[end + 1:]).strip())
    _validate_entry(entry)
    return entry


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.remove(temp_name)
        except OSError:
            pass
        raise


class MemoryAPI:
    def __init__(self, store: Path) -> None:
        self.store = Path(store).resolve()
        self.store.mkdir(parents=True, exist_ok=True)

    def _path(self, entry: MemoryEntry) -> Path:
        return self.store / entry.project / f"{entry.type}_{entry.name}__v0001.md"

    def _iter(self) -> Iterable[tuple[Path, MemoryEntry, int]]:
        for path in sorted(self.store.glob("*/*.md")):
            if path.name == "MEMORY.md":
                continue
            match = _FILE.fullmatch(path.name)
            if match is None:
                continue
            try:
                yield path, _parse(path), int(match.group("version") or "1")
            except (OSError, UnicodeDecodeError, ValueError):
                continue

    @staticmethod
    def _record(path: Path, entry: MemoryEntry, *, version: int, cross_project: bool) -> dict[str, Any]:
        age_days = max(0, int((datetime.now(timezone.utc).timestamp() - path.stat().st_mtime) // 86400))
        reference = f"{entry.project}/{entry.type}_{entry.name}@v{version:04d}"
        return {**entry.as_dict(), "path": path.as_posix(), "reference": reference,
                "version": version, "body_sha256": hashlib.sha256(entry.body.encode("utf-8")).hexdigest(),
                "age_days": age_days, "age_label": f"{age_days} days ago", "cross_project": cross_project}

    def read_index(self, *, project: str, scene: str, limit: int = 8) -> dict[str, Any]:
        return self.read(query=scene, project=project, scene=scene, limit=limit)

    def read(self, query: str, *, project: str, scene: str | None = None, memory_type: str | None = None,
             limit: int = 8, include_cross_project: bool = False) -> dict[str, Any]:
        if limit < 0 or limit > 100:
            raise ValueError("memory_limit_invalid")
        terms = {item.lower() for item in re.findall(r"[\w-]+", query) if len(item) > 1}
        local: list[dict[str, Any]] = []
        cross: list[dict[str, Any]] = []
        latest: dict[tuple[str, str, str], tuple[Path, MemoryEntry, int]] = {}
        for path, entry, version in self._iter():
            key = (entry.project, entry.type, entry.name)
            if key not in latest or version > latest[key][2]:
                latest[key] = (path, entry, version)
        for path, entry, version in latest.values():
            if scene and entry.scene != scene and entry.project == project:
                continue
            if memory_type and entry.type != memory_type:
                continue
            haystack = " ".join((entry.name, entry.description, entry.scene, entry.body)).lower()
            score = sum(term in haystack for term in terms)
            if terms and score == 0:
                continue
            is_cross = entry.project not in {project, "_shared"}
            if is_cross and not include_cross_project:
                continue
            record = self._record(path, entry, version=version, cross_project=is_cross)
            record["_score"] = score + (2 if entry.project == project else 1 if entry.project == "_shared" else 0)
            if entry.project in {project, "_shared"}:
                local.append(record)
            else:
                cross.append(record)
        local.sort(key=lambda item: (-item["_score"], item["age_days"], item["reference"]))
        cross.sort(key=lambda item: (-item["_score"], item["age_days"], item["reference"]))
        selected = local[:limit]
        if include_cross_project and len(selected) < limit:
            selected.extend(cross[:limit - len(selected)])
        for item in selected:
            item.pop("_score", None)
        return {"memories": selected, "local_memories": local[:limit], "cross_project_memories": cross[:limit]}

    def read_version(self, reference: str, *, max_chars: int = 20000) -> dict[str, Any]:
        if not isinstance(reference, str) or not _REFERENCE.fullmatch(reference):
            raise ValueError("memory_reference_invalid")
        match = _REFERENCE.fullmatch(reference)
        assert match is not None
        project = match.group("project")
        version = int(match.group("version"))
        stem = reference.split("/", 1)[1].rsplit("@v", 1)[0]
        path = (self.store / project / f"{stem}__v{version:04d}.md").resolve()
        if not path.is_file() and version == 1:
            # Read legacy v1 assets, but always expose the canonical versioned ref.
            legacy = (self.store / project / f"{stem}.md").resolve()
            if legacy.is_file():
                path = legacy
        if self.store not in path.parents:
            raise ValueError("memory_reference_outside_store")
        entry = _parse(path)
        body = entry.body[:max_chars]
        return {**entry.as_dict(), "path": path.as_posix(), "reference": reference,
                "version": version, "body_sha256": hashlib.sha256(entry.body.encode("utf-8")).hexdigest(),
                "truncated": len(body) < len(entry.body)}

    def write(self, entry: MemoryEntry, *, based_on: str | None = None) -> dict[str, Any]:
        _validate_entry(entry)
        versions = [version for path, existing, version in self._iter()
                    if existing.project == entry.project and existing.type == entry.type and existing.name == entry.name]
        latest = max(versions, default=0)
        if based_on is None:
            if latest:
                raise ValueError("memory_version_conflict")
            version = 1
        else:
            match = _REFERENCE.fullmatch(based_on)
            if match is None or match.group("project") != entry.project:
                raise ValueError("memory_based_on_invalid")
            stem = based_on.split("/", 1)[1].rsplit("@v", 1)[0]
            expected_stem = f"{entry.type}_{entry.name}"
            if stem != expected_stem or int(match.group("version")) != latest:
                raise ValueError("memory_based_on_not_latest")
            if latest == 0:
                raise ValueError("memory_based_on_not_found")
            version = latest + 1
        path = self.store / entry.project / f"{entry.type}_{entry.name}__v{version:04d}.md"
        if path.exists():
            raise ValueError("memory_version_conflict")
        _atomic_text(path, _render(entry))
        self.reindex()
        return {"written": True, "path": path.as_posix(),
                "reference": f"{entry.project}/{entry.type}_{entry.name}@v{version:04d}",
                "version": version, "name": entry.name, "project": entry.project, "type": entry.type, "based_on": based_on}

    def reindex(self) -> Path:
        groups: dict[str, list[str]] = {}
        latest: dict[tuple[str, str, str], tuple[Path, MemoryEntry, int]] = {}
        for path, entry, version in self._iter():
            key = (entry.project, entry.type, entry.name)
            if key not in latest or version > latest[key][2]:
                latest[key] = (path, entry, version)
        for path, entry, _version in latest.values():
            groups.setdefault(entry.project, []).append(
                f"- [{entry.description}]({path.relative_to(self.store).as_posix()}) — {entry.description}"
            )
        lines = ["# Memory Index", ""]
        for project in sorted(groups):
            lines.extend([f"## {project}", "", *sorted(groups[project]), ""])
        target = self.store / "MEMORY.md"
        _atomic_text(target, "\n".join(lines))
        return target
