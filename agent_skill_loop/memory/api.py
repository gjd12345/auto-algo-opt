"""Small, model-free auto-memory backend.

The agent decides whether an observation is worth retaining.  This module only
validates the five-field frontmatter, stores Markdown atomically, and performs
bounded deterministic retrieval.  It never calls a model and never changes
workflow state.
"""

from __future__ import annotations

import json

import os
import re
import tempfile
import hashlib
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
_FILE = re.compile(r"^(?P<type>insight|solution)_(?P<name>[A-Za-z0-9][A-Za-z0-9_-]{0,79}?)(?:__v(?P<version>[0-9]{4}))?\.md$")
_REFERENCE = re.compile(r"^(?P<project>[A-Za-z0-9_-]+|_shared)/(?:insight|solution)_[A-Za-z0-9][A-Za-z0-9_-]{0,79}@v(?P<version>[0-9]{4})$")
_SECRET = re.compile(r"(?i)(api[_-]?key|token|secret|password|access[_-]?token|bearer)\s*[:=]")
_FRONTMATTER = ("name", "description", "type", "project", "scene")
_SIDECAR_SCHEMA = "algorithm-optimization-memory-sidecar/v2"


def _metadata_object(path: Path) -> dict[str, Any]:
    metadata = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError("memory_metadata_invalid")
    return metadata


def _validate_metadata(metadata: dict[str, Any]) -> None:
    version = metadata.get("format_version")
    if version is not None and (type(version) is not int or version != 2):
        raise ValueError("memory_format_version_invalid")
    schema = metadata.get("schema")
    if (version == 2 or schema is not None) and (version != 2 or schema != _SIDECAR_SCHEMA):
        raise ValueError("memory_schema_invalid")
    for field in ("body_sha256", "content_sha256"):
        value = metadata.get(field)
        if field == "content_sha256" and value is None and version is None:
            continue
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError(f"memory_{field}_invalid")
    for field in ("operation_key", "based_on"):
        value = metadata.get(field)
        if value is not None and (not isinstance(value, str) or not value):
            raise ValueError("memory_metadata_invalid")
    refs = metadata.get("related_refs", [])
    if not isinstance(refs, list) or any(not isinstance(ref, str) or not _REFERENCE.fullmatch(ref) for ref in refs):
        raise ValueError("memory_metadata_invalid")
    _validate_provenance(metadata.get("provenance"))


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


def _validate_entry(entry: MemoryEntry, *, publication: bool = True) -> None:
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
    if not entry.body.strip() or len(entry.body) > 8000:
        raise ValueError("memory_body_invalid")
    if _SECRET.search(entry.description) or _SECRET.search(entry.body):
        raise ValueError("memory_sensitive_value")
    if not publication:
        return
    if entry.type == "insight":
        if "**Why:**" not in entry.body or "**How to apply:**" not in entry.body:
            raise ValueError("insight_body_sections_missing")
    if entry.type == "solution":
        if "**Reusable Experience:**" not in entry.body:
            raise ValueError("solution_reusable_experience_missing")
        if not any(heading in entry.body for heading in ("## Execution", "## 执行流程")):
            raise ValueError("solution_execution_section_missing")
        if "**Why:**" not in entry.body or "**How to apply:**" not in entry.body:
            raise ValueError("solution_body_sections_missing")


def _validate_provenance(provenance: Mapping[str, Any] | None) -> dict[str, str]:
    if provenance is None:
        return {}
    if not isinstance(provenance, Mapping):
        raise ValueError("memory_provenance_invalid")
    result: dict[str, str] = {}
    for key, value in provenance.items():
        if not isinstance(key, str) or not key or len(key) > 80:
            raise ValueError("memory_provenance_invalid")
        if not isinstance(value, str) or not value or len(value) > 1024:
            raise ValueError("memory_provenance_invalid")
        result[key] = value
    return dict(sorted(result.items()))


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
    # Historical entries remain readable even if they predate the current
    # body template. New publications are checked by _write_locked(), and v2
    # sidecars opt into strict read-time format validation.
    _validate_entry(entry, publication=False)
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

    def _iter(self, diagnostics: list[dict[str, str]] | None = None) -> Iterable[tuple[Path, MemoryEntry, int]]:
        # Select the highest observed revision BEFORE validating its contents.
        # A damaged current revision must not resurrect superseded advice.
        # An orphan sidecar also reserves its revision until explicitly repaired.
        latest: dict[tuple[str, str, str], tuple[int, bool, Path]] = {}
        for asset in sorted(self.store.glob("*/*")):
            if asset.suffix not in {".md", ".json"}:
                continue
            path = asset.with_suffix(".md")
            match = _FILE.fullmatch(path.name)
            if match is None:
                continue
            key = (path.parent.name, match.group("type"), match.group("name"))
            rank = (int(match.group("version") or "1"), match.group("version") is not None)
            if key not in latest or rank > latest[key][:2]:
                latest[key] = (*rank, path)
        for version, _versioned, path in latest.values():
            if not path.resolve().is_relative_to(self.store):
                continue
            if path.name == "MEMORY.md":
                continue
            match = _FILE.fullmatch(path.name)
            if match is None:
                continue
            try:
                entry = _parse(path)
                if (entry.project, entry.type, entry.name) != (path.parent.name, match.group("type"), match.group("name")):
                    raise ValueError("memory_reference_identity_mismatch")
                metadata = self._verify_metadata(path, entry)
                if metadata.get("format_version") == 2:
                    _validate_entry(entry)
                yield path, entry, version
            except (OSError, UnicodeDecodeError, ValueError) as exc:
                if diagnostics is not None and len(diagnostics) < 32:
                    diagnostics.append({
                        "reference_hint": path.relative_to(self.store).as_posix(),
                        "error_code": str(exc)[:128] if isinstance(exc, ValueError) else type(exc).__name__,
                    })
                continue

    @staticmethod
    def _verify_metadata(path: Path, entry: MemoryEntry) -> dict[str, Any]:
        metadata_path = path.with_suffix(".json")
        if not metadata_path.is_file():
            match = _FILE.fullmatch(path.name)
            if match is not None and match.group("version") is not None:
                raise ValueError("memory_metadata_missing")
            # Only the historical unversioned filename is accepted without a
            # sidecar. It remains explicitly unverified in read results.
            return {"integrity": "legacy_unverified"}
        metadata = _metadata_object(metadata_path)
        _validate_metadata(metadata)
        body_hash = hashlib.sha256(entry.body.encode("utf-8")).hexdigest()
        if metadata.get("body_sha256") != body_hash:
            raise ValueError("memory_body_hash_mismatch")
        content_hash = metadata.get("content_sha256")
        if content_hash is not None and content_hash != hashlib.sha256(_render(entry).encode("utf-8")).hexdigest():
            raise ValueError("memory_content_hash_mismatch")
        metadata["integrity"] = "verified" if content_hash is not None else "legacy_body_verified"
        return metadata

    @staticmethod
    def _record(path: Path, entry: MemoryEntry, *, version: int, cross_project: bool) -> dict[str, Any]:
        age_days = max(0, int((datetime.now(timezone.utc).timestamp() - path.stat().st_mtime) // 86400))
        reference = f"{entry.project}/{entry.type}_{entry.name}@v{version:04d}"
        return {**entry.as_dict(), "path": path.as_posix(), "reference": reference,
                "version": version, "body_sha256": hashlib.sha256(entry.body.encode("utf-8")).hexdigest(),
                "age_days": age_days, "age_label": f"{age_days} days ago", "cross_project": cross_project}

    def read_index(self, *, project: str, scene: str, limit: int = 8) -> dict[str, Any]:
        result = self.read(query=scene, project=project, scene=scene, limit=limit)
        for key in ("memories", "local_memories", "cross_project_memories"):
            result[key] = [{k: v for k, v in row.items() if k != "body"} for row in result[key]]
        return result

    def read(self, query: str, *, project: str, scene: str | None = None, memory_type: str | None = None,
             limit: int = 8, include_cross_project: bool = False, offset: int = 0,
             include_shared: bool = True) -> dict[str, Any]:
        if limit < 0 or limit > 100:
            raise ValueError("memory_limit_invalid")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("memory_offset_invalid")
        terms = {item.lower() for item in re.findall(r"[\w-]+", query) if len(item) > 1}
        local: list[dict[str, Any]] = []
        cross: list[dict[str, Any]] = []
        latest: dict[tuple[str, str, str], tuple[Path, MemoryEntry, int]] = {}
        diagnostics: list[dict[str, str]] = []
        for path, entry, version in self._iter(diagnostics):
            key = (entry.project, entry.type, entry.name)
            if key not in latest or version > latest[key][2]:
                latest[key] = (path, entry, version)
        for path, entry, version in latest.values():
            if entry.project == "_shared" and not include_shared:
                continue
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
        pool = local + cross if include_cross_project else local
        selected = pool[offset:offset + limit]
        for item in selected:
            item.pop("_score", None)
        return {"memories": selected, "local_memories": local[:limit], "cross_project_memories": cross[:limit],
                "degraded": bool(diagnostics), "diagnostics": diagnostics[:32]}

    def read_version(self, reference: str, *, max_chars: int = 8000, offset: int = 0) -> dict[str, Any]:
        if isinstance(max_chars, bool) or not isinstance(max_chars, int) or not 1 <= max_chars <= 8000 or isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("memory_page_invalid")
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
        if f"{entry.project}/{entry.type}_{entry.name}@v{version:04d}" != reference:
            raise ValueError("memory_reference_identity_mismatch")
        metadata = self._verify_metadata(path, entry)
        if metadata.get("format_version") == 2:
            _validate_entry(entry)
        age_days = max(0, int((datetime.now(timezone.utc).timestamp() - path.stat().st_mtime) // 86400))
        body = entry.body[offset:offset + max_chars]
        return {**entry.as_dict(), "body": body, "path": path.as_posix(), "reference": reference,
                "version": version, "body_sha256": hashlib.sha256(entry.body.encode("utf-8")).hexdigest(),
                "based_on": metadata.get("based_on"),
                "related_refs": list(metadata.get("related_refs") or []),
                "provenance": dict(metadata.get("provenance") or {}),
                "integrity": metadata.get("integrity", "legacy_unverified"),
                "format_status": "current" if metadata.get("format_version") == 2 else "legacy_compatible",
                "age_days": age_days, "age_label": f"{age_days} days ago",
                "returned_body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                "offset": offset, "total_chars": len(entry.body),
                "next_offset": offset + len(body) if offset + len(body) < len(entry.body) else None,
                "truncated": offset != 0 or len(body) < len(entry.body)}

    @contextmanager
    def _writer(self):
        from agent_skill_loop.file_lock import exclusive_file_lock
        with exclusive_file_lock(self.store / ".writer.lock", busy="memory_writer_busy", legacy_pid=True):
            yield

    def write(self, entry: MemoryEntry, *, based_on: str | None = None,
              related_refs: tuple[str, ...] = (), provenance: Mapping[str, Any] | None = None,
              operation_key: str | None = None) -> dict[str, Any]:
        # The parser exposes a stripped body; publish and idempotency must use
        # that same representation, including for crash-replayed submissions.
        entry = replace(entry, body=entry.body.strip())
        _validate_entry(entry)
        provenance = _validate_provenance(provenance)
        # based_on is a CAS update of the SAME entry; related_refs are provenance
        # for a new or merged full snapshot. Previous versions are never removed.
        with self._writer():
            if operation_key:
                for metadata_path in sorted(self.store.glob("*/*.json")):
                    try:
                        stored = _metadata_object(metadata_path)
                    except (OSError, UnicodeDecodeError, ValueError):
                        continue
                    if stored.get("operation_key") != operation_key:
                        continue
                    path = metadata_path.with_suffix(".md")
                    match = _FILE.fullmatch(path.name)
                    if match is None or not path.is_file():
                        raise ValueError("memory_operation_evidence_missing")
                    existing = _parse(path)
                    self._verify_metadata(path, existing)
                    version = int(match.group("version") or "1")
                    if existing != entry or dict(stored.get("provenance") or {}) != provenance:
                        raise ValueError("memory_operation_conflict")
                    return {"written": True, "reference": f"{entry.project}/{entry.type}_{entry.name}@v{version:04d}", "version": version, "replayed": True}
            for ref in related_refs:
                self.read_version(ref)
            result = self._write_locked(entry, based_on=based_on, related_refs=related_refs,
                                        provenance=provenance, operation_key=operation_key)
            result["related_refs"] = list(related_refs)
            return result

    def _write_locked(self, entry: MemoryEntry, *, based_on: str | None = None,
                      related_refs: tuple[str, ...] = (), provenance: Mapping[str, str] | None = None,
                      operation_key: str | None = None) -> dict[str, Any]:
        _validate_entry(entry)
        versions = []
        for path in self.store.glob(f"{entry.project}/{entry.type}_{entry.name}*"):
            if path.suffix not in {".md", ".json"}:
                continue
            match = _FILE.fullmatch(path.with_suffix(".md").name)
            if match is not None and match.group("type") == entry.type and match.group("name") == entry.name:
                versions.append(int(match.group("version") or "1"))
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
            self.read_version(based_on)
            version = latest + 1
        path = self.store / entry.project / f"{entry.type}_{entry.name}__v{version:04d}.md"
        if not path.resolve().is_relative_to(self.store) or not path.with_suffix(".json").resolve().is_relative_to(self.store):
            raise ValueError("memory_reference_outside_store")
        if path.exists():
            raise ValueError("memory_version_conflict")
        rendered = _render(entry)
        _atomic_text(path.with_suffix(".json"), json.dumps({"schema": "algorithm-optimization-memory-sidecar/v2", "format_version": 2,
                     "based_on": based_on, "related_refs": list(related_refs),
                     "provenance": dict(provenance or {}), "operation_key": operation_key,
                     "update_semantics": "full_snapshot", "body_sha256": hashlib.sha256(entry.body.encode("utf-8")).hexdigest(),
                     "content_sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest()}))
        _atomic_text(path, rendered)
        index_error = None
        try:
            self.reindex()
        except OSError as exc:
            # Version files are authoritative; the index is rebuildable.
            index_error = type(exc).__name__
        return {"written": True, "path": path.as_posix(),
                "index_updated": index_error is None, "index_error": index_error,
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
