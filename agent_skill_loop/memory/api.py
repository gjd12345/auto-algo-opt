"""Small, model-free auto-memory backend.

The agent decides whether an observation is worth retaining.  This module only
validates card content and sidecars, publishes recoverable snapshots, and performs
bounded deterministic retrieval.  It never calls a model and never changes
workflow state.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .problem_vocab import validate_problem_vocab

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
_CARD_TYPE = r"insight|solution|antipattern"
MEMORY_CARD_TYPES = frozenset(_CARD_TYPE.split("|"))
_FILE = re.compile(rf"^(?P<type>{_CARD_TYPE})_(?P<name>[A-Za-z0-9][A-Za-z0-9_-]{{0,79}}?)(?:__v(?P<version>[0-9]{{4}}))?\.md$")
_REFERENCE = re.compile(rf"^(?P<project>[A-Za-z0-9_-]+)/(?:{_CARD_TYPE})_[A-Za-z0-9][A-Za-z0-9_-]{{0,79}}@v(?P<version>[0-9]{{4}})$")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SECRET = re.compile(r"(?i)(api[_-]?key|token|secret|password|access[_-]?token|bearer)\s*[:=]")
_FRONTMATTER = ("name", "description", "type", "project", "scene")
_SIDECAR_SCHEMA = {version: f"algorithm-optimization-memory-sidecar/v{version}" for version in (2, 3)}
_V3_FIELDS = ("applicability_scope", "validity_status", "evidence_tier", "code_anchor")
_SCOPE_IDENTITY = ("problem", "interface_id", "fleet_policy", "evaluator_version")
_SCOPE_RANGES = ("n_range", "budget_ms_range")
_SCOPE_FIELDS = {*_SCOPE_IDENTITY, *_SCOPE_RANGES, "expires_at_utc", "reentry_rule"}
_VALIDITY_STATUSES = {"active", "stale_code_drift", "stale_metric_regression", "superseded", "quarantined"}
_EVIDENCE_TIERS = {"single_run", "common_fork_verified", "multi_seed_verified", "kb_promoted"}
_ANTIPATTERN_SECTIONS = ("Root Cause", "Applicability Scope", "Guardrail & False-Positive Boundary")
_MAX_SCOPE_LIFETIME = timedelta(days=365)
_PENDING_SUFFIX = ".publish"


class MemoryPublicationPending(OSError):
    """A durable stage or visible publication exists and can be replayed."""


def _scope_expiry(scope: Mapping[str, Any]) -> datetime | None:
    if "expires_at_utc" not in scope:
        return None
    value = scope["expires_at_utc"]
    try:
        expiry = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("memory_scope_expiry_invalid") from None
    if expiry.utcoffset() != timedelta(0):
        raise ValueError("memory_scope_expiry_invalid")
    return expiry


def _bounded_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 512 and not _SECRET.search(value)


def _scope_number(value: Any, *, integer: bool = False) -> bool:
    return (type(value) is int or (not integer and type(value) is float and math.isfinite(value))) and value >= 0


def _validate_scope(scope: Any, *, project: str, required: bool) -> None:
    if not isinstance(scope, Mapping) or not scope or set(scope) - _SCOPE_FIELDS:
        raise ValueError("memory_applicability_scope_invalid")
    if required and set(scope) != _SCOPE_FIELDS:
        raise ValueError("memory_applicability_scope_incomplete")
    for key in (*_SCOPE_IDENTITY, "reentry_rule"):
        if key in scope and not _bounded_text(scope[key]):
            raise ValueError("memory_applicability_scope_invalid")
    if "problem" in scope and scope["problem"] != project:
        raise ValueError("memory_applicability_problem_mismatch")
    for key in _SCOPE_RANGES:
        if key in scope:
            bounds = scope[key]
            if (not isinstance(bounds, (list, tuple)) or len(bounds) != 2
                    or not all(_scope_number(value, integer=key == "n_range") for value in bounds)
                    or bounds[0] > bounds[1]):
                raise ValueError("memory_applicability_range_invalid")
    _scope_expiry(scope)
    if "reentry_rule" in scope:
        validate_problem_vocab(project, scope["reentry_rule"])


def _validate_anchor(anchor: Any) -> None:
    if (not isinstance(anchor, Mapping) or not anchor
            or set(anchor) - {"code_sha256", "canonical_ast_sha256"}
            or any(not isinstance(value, str) or not _SHA256.fullmatch(value) for value in anchor.values())):
        raise ValueError("memory_code_anchor_invalid")


def memory_is_active(card: Mapping[str, Any], context: Mapping[str, Any] | None = None) -> bool:
    """Evaluate stored typed predicates using trusted runtime data when supplied."""
    if card.get("enabled") is False or card.get("validity_status", "active") != "active":
        return False
    scope = card.get("applicability_scope")
    if not scope:
        return True
    expiry = _scope_expiry(scope)
    if expiry is not None and datetime.now(timezone.utc) >= expiry:
        return False
    if context is None:
        return True
    if any(key in scope and scope[key] != context.get(key) for key in _SCOPE_IDENTITY):
        return False
    for range_key, value_key in (("n_range", "n"), ("budget_ms_range", "budget_ms")):
        if range_key not in scope:
            continue
        value = context.get(value_key)
        values = value if value_key == "n" and isinstance(value, tuple) else (value,)
        lower, upper = scope[range_key]
        if not values or not all(_scope_number(item, integer=value_key == "n") and lower <= item <= upper
                                 for item in values):
            return False
    return True


def _metadata_object(path: Path) -> dict[str, Any]:
    metadata = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError("memory_metadata_invalid")
    return metadata


def _validate_metadata(metadata: dict[str, Any]) -> None:
    version = metadata.get("format_version")
    if version is not None and (type(version) is not int or version not in _SIDECAR_SCHEMA):
        raise ValueError("memory_format_version_invalid")
    schema = metadata.get("schema")
    if schema != _SIDECAR_SCHEMA.get(version):
        raise ValueError("memory_schema_invalid")
    for field in ("body_sha256", "content_sha256"):
        value = metadata.get(field)
        if field == "content_sha256" and value is None and version is None:
            continue
        if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
            raise ValueError(f"memory_{field}_invalid")
    if any(key in metadata for key in _V3_FIELDS) and version != 3:
        raise ValueError("memory_format_version_invalid")
    if "enabled" in metadata and type(metadata["enabled"]) is not bool:
        raise ValueError("memory_enabled_invalid")
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
    applicability_scope: Mapping[str, Any] | None = None
    validity_status: str | None = None
    evidence_tier: str | None = None
    code_anchor: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "description": self.description, "type": self.type,
            "project": self.project, "scene": self.scene, "body": self.body,
            **{key: getattr(self, key) for key in _V3_FIELDS if getattr(self, key) is not None},
        }


def _validate_context_vocab(entry: MemoryEntry, context: Mapping[str, Any] | None) -> None:
    project = context.get("problem") if context is not None else None
    if isinstance(project, str):
        scope = entry.applicability_scope or {}
        validate_problem_vocab(project, entry.name, entry.description, entry.body, scope.get("reentry_rule", ""))


def _validate_entry(entry: MemoryEntry, *, publication: bool = True, vocab: bool = True) -> None:
    if not _NAME.fullmatch(entry.name):
        raise ValueError("memory_name_invalid")
    if entry.type not in MEMORY_CARD_TYPES:
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
    if vocab:
        validate_problem_vocab(entry.project, entry.name, entry.description, entry.body)
    required = entry.type == "antipattern"
    if required or entry.applicability_scope is not None:
        _validate_scope(entry.applicability_scope, project=entry.project, required=required)
    if required or entry.code_anchor is not None:
        _validate_anchor(entry.code_anchor)
    if required or entry.validity_status is not None:
        if not isinstance(entry.validity_status, str) or entry.validity_status not in _VALIDITY_STATUSES:
            raise ValueError("memory_validity_status_invalid")
    if required or entry.evidence_tier is not None:
        if not isinstance(entry.evidence_tier, str) or entry.evidence_tier not in _EVIDENCE_TIERS:
            raise ValueError("memory_evidence_tier_invalid")
    if required:
        sections = _antipattern_sections(entry.body)
        if any(not sections.get(section) for section in _ANTIPATTERN_SECTIONS):
            raise ValueError("antipattern_body_sections_missing")
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


def _antipattern_sections(body: str) -> dict[str, str]:
    sections = {}
    # Fenced examples are not section declarations.
    heading = None
    fence = None
    for line in body.splitlines():
        if marker := re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line):
            delimiter, trailing = marker.groups()
            if fence is None:
                fence = delimiter
            elif delimiter[0] == fence[0] and len(delimiter) >= len(fence) and not trailing.strip():
                fence = None
            continue
        if fence is not None:
            continue
        if match := re.match(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$", line):
            heading = match[2] if match[1] == "##" else None
        elif heading and line.strip():
            sections[heading] = line.strip()
    return sections


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


def _parse_text(text: str) -> MemoryEntry:
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
    # body template. New publications are checked by write(), and v2/v3
    # sidecars opt into strict read-time format validation.
    _validate_entry(entry, publication=False)
    return entry


def _parse(path: Path) -> MemoryEntry:
    return _parse_text(path.read_text(encoding="utf-8"))


def _sync_directory(path: Path) -> None:
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
        _sync_directory(path.parent)
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
        if next(self.store.glob(f"*/*{_PENDING_SUFFIX}"), None) is not None:
            try:
                with self._writer():
                    pass
            except ValueError as exc:
                if str(exc) != "memory_writer_busy":
                    raise

    def _path(self, entry: MemoryEntry) -> Path:
        return self.store / entry.project / f"{entry.type}_{entry.name}__v0001.md"

    def _iter(self, diagnostics: list[dict[str, str]] | None = None
              ) -> Iterable[tuple[Path, MemoryEntry, int, dict[str, Any]]]:
        # Select the highest observed revision BEFORE validating its contents.
        # A damaged current revision must not resurrect superseded advice.
        # An orphan sidecar also reserves its revision until explicitly repaired.
        latest: dict[tuple[str, str, str], tuple[int, bool, Path]] = {}
        for asset in sorted(self.store.glob("*/*")):
            if asset.suffix not in {".md", ".json", _PENDING_SUFFIX}:
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
                entry, metadata = self._load_entry(path)
                if (entry.project, entry.type, entry.name) != (path.parent.name, match.group("type"), match.group("name")):
                    raise ValueError("memory_reference_identity_mismatch")
                if memory_is_active(metadata):
                    yield path, entry, version, metadata
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
        if metadata_path.is_symlink() or not metadata_path.resolve().is_relative_to(path.parent.resolve()):
            raise ValueError("memory_reference_outside_store")
        if not metadata_path.is_file():
            match = _FILE.fullmatch(path.name)
            if match is not None and match.group("version") is not None:
                raise ValueError("memory_metadata_missing")
            # Only the historical unversioned filename is accepted without a
            # sidecar. It remains explicitly unverified in read results.
            return {"integrity": "legacy_unverified"}
        metadata = _metadata_object(metadata_path)
        MemoryAPI._verify_content(entry, metadata)
        metadata["integrity"] = "verified" if metadata.get("content_sha256") is not None else "legacy_body_verified"
        return metadata

    @staticmethod
    def _verify_content(entry: MemoryEntry, metadata: dict[str, Any]) -> None:
        _validate_metadata(metadata)
        body_hash = hashlib.sha256(entry.body.encode("utf-8")).hexdigest()
        if metadata.get("body_sha256") != body_hash:
            raise ValueError("memory_body_hash_mismatch")
        content_hash = metadata.get("content_sha256")
        if content_hash is not None and content_hash != hashlib.sha256(_render(entry).encode("utf-8")).hexdigest():
            raise ValueError("memory_content_hash_mismatch")

    def _load_entry(self, path: Path) -> tuple[MemoryEntry, dict[str, Any]]:
        entry = _parse(path)
        metadata = self._verify_metadata(path, entry)
        version = metadata.get("format_version")
        if entry.type == "antipattern" and version != 3:
            raise ValueError("memory_format_version_invalid")
        if version in _SIDECAR_SCHEMA:
            fields = {key: metadata[key] for key in _V3_FIELDS if key in metadata}
            if any(value is None for value in fields.values()):
                raise ValueError("memory_structured_metadata_invalid")
            entry = replace(entry, **fields)
            _validate_entry(entry, vocab=version == 3)
        return entry, metadata

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
             include_shared: bool = True, applicability_context: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if limit < 0 or limit > 100:
            raise ValueError("memory_limit_invalid")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("memory_offset_invalid")
        terms = {item.lower() for item in re.findall(r"[\w-]+", query) if len(item) > 1}
        local: list[dict[str, Any]] = []
        cross: list[dict[str, Any]] = []
        diagnostics: list[dict[str, str]] = []
        for path, entry, version, metadata in self._iter(diagnostics):
            if not memory_is_active(metadata, applicability_context):
                continue
            try:
                _validate_context_vocab(entry, applicability_context)
            except ValueError:
                continue
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
            if "format_version" in metadata:
                record["format_version"] = metadata["format_version"]
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

    def read_version(self, reference: str, *, max_chars: int = 8000, offset: int = 0,
                     require_active: bool = False,
                     applicability_context: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if require_active:
            with self._writer():
                return self._read_version(reference, max_chars=max_chars, offset=offset, require_active=True,
                                          applicability_context=applicability_context)
        return self._read_version(reference, max_chars=max_chars, offset=offset)

    def _read_version(self, reference: str, *, max_chars: int, offset: int, require_active: bool = False,
                      applicability_context: Mapping[str, Any] | None = None) -> dict[str, Any]:
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
        entry, metadata = self._load_entry(path)
        if f"{entry.project}/{entry.type}_{entry.name}@v{version:04d}" != reference:
            raise ValueError("memory_reference_identity_mismatch")
        if require_active:
            if not memory_is_active(metadata, applicability_context):
                raise ValueError("memory_reference_inactive")
            if reference != self.card_head(entry):
                raise ValueError("memory_reference_superseded")
            _validate_context_vocab(entry, applicability_context)
        age_days = max(0, int((datetime.now(timezone.utc).timestamp() - path.stat().st_mtime) // 86400))
        body = entry.body[offset:offset + max_chars]
        return {**entry.as_dict(), "body": body, "path": path.as_posix(), "reference": reference,
                "version": version, "body_sha256": hashlib.sha256(entry.body.encode("utf-8")).hexdigest(),
                "based_on": metadata.get("based_on"),
                "related_refs": list(metadata.get("related_refs") or []),
                "provenance": dict(metadata.get("provenance") or {}),
                "integrity": metadata.get("integrity", "legacy_unverified"),
                "format_status": "current" if metadata.get("format_version") in _SIDECAR_SCHEMA else "legacy_compatible",
                **{key: metadata[key] for key in ("format_version", "enabled") if key in metadata},
                "age_days": age_days, "age_label": f"{age_days} days ago",
                "returned_body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                "offset": offset, "total_chars": len(entry.body),
                "next_offset": offset + len(body) if offset + len(body) < len(entry.body) else None,
                "truncated": offset != 0 or len(body) < len(entry.body)}

    @contextmanager
    def _writer(self):
        from agent_skill_loop.file_lock import exclusive_file_lock
        with exclusive_file_lock(self.store / ".writer.lock", busy="memory_writer_busy", legacy_pid=True):
            if self._recover_publications():
                try:
                    self.reindex()
                except OSError:
                    pass  # Version files are authoritative; the index is rebuildable.
            yield

    def _recover_publications(self) -> bool:
        recovered = False
        for pending in sorted(self.store.glob(f"*/*{_PENDING_SUFFIX}")):
            try:
                self._finish_publication(pending)
                recovered = True
            except (ValueError, OSError):
                # An invalid or unwritable stage reserves its version. Preserve
                # the evidence, and let independent cards remain usable.
                continue
        return recovered

    def _check_publication_paths(self, path: Path) -> None:
        for asset in (path, path.with_suffix(".json"), path.with_suffix(_PENDING_SUFFIX)):
            if asset.is_symlink() or not asset.resolve().is_relative_to(self.store):
                raise ValueError("memory_reference_outside_store")

    def _stage_publication(self, path: Path, rendered: str, metadata: dict[str, Any]) -> None:
        self._check_publication_paths(path)
        if not path.parent.exists():
            path.parent.mkdir()
            _sync_directory(self.store)
        pending = path.with_suffix(_PENDING_SUFFIX)
        if pending.exists():
            raise ValueError("memory_publication_conflict")
        try:
            _atomic_text(pending, json.dumps({"markdown": rendered, "sidecar": metadata}, ensure_ascii=False))
            self._finish_publication(pending)
        except OSError as exc:
            if pending.is_file() or path.is_file():
                raise MemoryPublicationPending("memory_publication_pending") from exc
            raise

    def _finish_publication(self, pending: Path) -> None:
        path = pending.with_suffix(".md")
        self._check_publication_paths(path)
        match = _FILE.fullmatch(path.name)
        if match is None or match.group("version") is None:
            raise ValueError("memory_publication_path_invalid")
        journal = _metadata_object(pending)
        markdown, metadata = journal.get("markdown"), journal.get("sidecar")
        if not isinstance(markdown, str) or not isinstance(metadata, dict):
            raise ValueError("memory_publication_invalid")
        entry = _parse_text(markdown)
        if ((entry.project, entry.type, entry.name) != (path.parent.name, match["type"], match["name"])
                or markdown != _render(entry)):
            raise ValueError("memory_reference_identity_mismatch")
        self._verify_content(entry, metadata)
        if metadata.get("format_version") not in _SIDECAR_SCHEMA:
            raise ValueError("memory_format_version_invalid")
        fields = {key: metadata[key] for key in _V3_FIELDS if key in metadata}
        if any(value is None for value in fields.values()):
            raise ValueError("memory_structured_metadata_invalid")
        _validate_entry(replace(entry, **fields), vocab=metadata["format_version"] == 3)
        sidecar = path.with_suffix(".json")
        if ((sidecar.exists() and _metadata_object(sidecar) != metadata)
                or (path.exists() and path.read_text(encoding="utf-8") != markdown)):
            raise ValueError("memory_publication_conflict")
        # The Markdown rename is the visibility point. The journal remains
        # intact until both final files are installed and synced.
        if not sidecar.exists():
            _atomic_text(sidecar, json.dumps(metadata, ensure_ascii=False))
        if not path.exists():
            _atomic_text(path, markdown)
        pending.unlink()
        _sync_directory(path.parent)

    def card_head(self, entry: MemoryEntry) -> str | None:
        """Return the latest observed same-card version, including damaged heads."""
        _validate_entry(entry, publication=False)
        latest = 0
        for path in self.store.glob(f"{entry.project}/{entry.type}_{entry.name}*"):
            if path.suffix not in {".md", ".json", _PENDING_SUFFIX}:
                continue
            match = _FILE.fullmatch(path.with_suffix(".md").name)
            if match is not None and match["type"] == entry.type and match["name"] == entry.name:
                latest = max(latest, int(match["version"] or "1"))
        return f"{entry.project}/{entry.type}_{entry.name}@v{latest:04d}" if latest else None

    def write(self, entry: MemoryEntry, *, based_on: str | None = None,
              related_refs: tuple[str, ...] = (), provenance: Mapping[str, Any] | None = None,
              operation_key: str | None = None, format_version: int | None = None) -> dict[str, Any]:
        # The parser exposes a stripped body; publish and idempotency must use
        # that same representation, including for crash-replayed submissions.
        entry = replace(entry, body="\n".join(entry.body.splitlines()).strip())
        _validate_entry(entry)
        if entry.applicability_scope is not None:
            scope = dict(entry.applicability_scope)
            for key in _SCOPE_RANGES:
                if key in scope:
                    scope[key] = list(scope[key])
            expiry = _scope_expiry(scope)
            if expiry is not None and expiry > datetime.now(timezone.utc) + _MAX_SCOPE_LIFETIME:
                raise ValueError("memory_scope_expiry_too_far")
            entry = replace(entry, applicability_scope=scope)
        if entry.code_anchor is not None:
            entry = replace(entry, code_anchor=dict(entry.code_anchor))
        if format_version is not None and (type(format_version) is not int or format_version not in _SIDECAR_SCHEMA):
            raise ValueError("memory_format_version_invalid")
        if any(getattr(entry, key) is not None for key in _V3_FIELDS):
            if format_version == 2:
                raise ValueError("memory_format_version_invalid")
            format_version = 3
        provenance = _validate_provenance(provenance)
        # based_on is a CAS update of the SAME entry; related_refs are provenance
        # for a new or merged full snapshot. Previous versions are never removed.
        with self._writer():
            if operation_key:
                for pending in sorted(self.store.glob(f"*/*{_PENDING_SUFFIX}")):
                    try:
                        staged = _metadata_object(pending).get("sidecar")
                    except (OSError, ValueError):
                        continue
                    if isinstance(staged, dict) and staged.get("operation_key") == operation_key:
                        raise MemoryPublicationPending("memory_publication_pending")
                for metadata_path in sorted(self.store.glob("*/*.json")):
                    try:
                        stored = _metadata_object(metadata_path)
                    except (OSError, UnicodeDecodeError, ValueError):
                        continue
                    if stored.get("operation_key") != operation_key:
                        continue
                    _validate_metadata(stored)
                    path = metadata_path.with_suffix(".md")
                    self._check_publication_paths(path)
                    match = _FILE.fullmatch(path.name)
                    if match is None or (entry.project, entry.type, entry.name) != (path.parent.name, match["type"], match["name"]):
                        raise ValueError("memory_operation_evidence_missing")
                    if (dict(stored.get("provenance") or {}) != provenance
                            or stored.get("based_on") != based_on
                            or stored.get("related_refs", []) != list(related_refs)
                            or (format_version is not None and stored.get("format_version") != format_version)):
                        raise ValueError("memory_operation_conflict")
                    if not path.is_file():
                        # Old writers installed the sidecar first without a journal.
                        # Only the original operation can prove the exact Markdown.
                        self._verify_content(entry, stored)
                        self._stage_publication(path, _render(entry), stored)
                        try:
                            self.reindex()
                        except OSError:
                            pass
                    existing, _metadata = self._load_entry(path)
                    version = int(match.group("version") or "1")
                    if existing != entry:
                        raise ValueError("memory_operation_conflict")
                    return {"written": True, "reference": f"{entry.project}/{entry.type}_{entry.name}@v{version:04d}",
                            "version": version, "format_version": stored.get("format_version"), "replayed": True}
            for ref in related_refs:
                self.read_version(ref)
            result = self._write_locked(entry, based_on=based_on, related_refs=related_refs,
                                        provenance=provenance, operation_key=operation_key, format_version=format_version)
            result["related_refs"] = list(related_refs)
            return result

    def _write_locked(self, entry: MemoryEntry, *, based_on: str | None = None,
                      related_refs: tuple[str, ...] = (), provenance: Mapping[str, str] | None = None,
                      operation_key: str | None = None, format_version: int | None = None) -> dict[str, Any]:
        head = self.card_head(entry)
        if based_on is None:
            if head is not None:
                raise ValueError("memory_version_conflict")
            version = 1
        else:
            match = _REFERENCE.fullmatch(based_on)
            if match is None or match.group("project") != entry.project:
                raise ValueError("memory_based_on_invalid")
            if based_on != head:
                raise ValueError("memory_based_on_not_latest")
            previous = self.read_version(based_on)
            if previous.get("format_version") == 3 and format_version == 2:
                raise ValueError("memory_format_version_downgrade")
            format_version = format_version or previous.get("format_version")
            version = previous["version"] + 1
        if version > 9999:
            raise ValueError("memory_version_limit")
        format_version = format_version or 2
        path = self.store / entry.project / f"{entry.type}_{entry.name}__v{version:04d}.md"
        self._check_publication_paths(path)
        if path.exists():
            raise ValueError("memory_version_conflict")
        rendered = _render(entry)
        metadata = {
            "schema": _SIDECAR_SCHEMA[format_version], "format_version": format_version,
            "based_on": based_on, "related_refs": list(related_refs),
            "provenance": dict(provenance or {}), "operation_key": operation_key,
            "update_semantics": "full_snapshot", "body_sha256": hashlib.sha256(entry.body.encode("utf-8")).hexdigest(),
            "content_sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
            **{key: getattr(entry, key) for key in _V3_FIELDS if getattr(entry, key) is not None},
        }
        self._stage_publication(path, rendered, metadata)
        index_error = None
        try:
            self.reindex()
        except OSError as exc:
            # Version files are authoritative; the index is rebuildable.
            index_error = type(exc).__name__
        return {"written": True, "path": path.as_posix(),
                "index_updated": index_error is None, "index_error": index_error,
                "reference": f"{entry.project}/{entry.type}_{entry.name}@v{version:04d}",
                "version": version, "format_version": format_version, "name": entry.name,
                "project": entry.project, "type": entry.type, "based_on": based_on}

    def reindex(self) -> Path:
        groups: dict[str, list[str]] = {}
        for path, entry, _version, _metadata in self._iter():
            groups.setdefault(entry.project, []).append(
                f"- [{entry.description}]({path.relative_to(self.store).as_posix()}) — {entry.description}"
            )
        lines = ["# Memory Index", ""]
        for project in sorted(groups):
            lines.extend([f"## {project}", "", *sorted(groups[project]), ""])
        target = self.store / "MEMORY.md"
        _atomic_text(target, "\n".join(lines))
        return target
