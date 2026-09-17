"""Strict bounded JSON and byte-preserving envelope extraction."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import sys

CANONICALIZATION = "optics-json-c14n-py312/v1"
MAX_BYTES = 1_000_000


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def require_python() -> None:
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("PYTHON_312_REQUIRED")


def canonical(value: object) -> bytes:
    require_python()
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _pairs(items):
    obj = {}
    for key, value in items:
        if key in obj:
            raise ValueError("DUPLICATE_JSON_KEY")
        obj[key] = value
    return obj


def _number(token, converter):
    if len(token) > 4300:
        raise ValueError("NUMBER_TOKEN_LIMIT")
    result = converter(token)
    if isinstance(result, float) and not math.isfinite(result):
        raise ValueError("NONFINITE_NUMBER")
    return result


def _constant(token):
    raise ValueError("NONFINITE_NUMBER")


DECODER = json.JSONDecoder(object_pairs_hook=_pairs, parse_constant=_constant,
                          parse_int=lambda s: _number(s, int),
                          parse_float=lambda s: _number(s, float))


def strict(raw: bytes, limit: int = MAX_BYTES) -> object:
    if len(raw) > limit:
        raise ValueError("JSON_SIZE_LIMIT")
    text = raw.decode("utf-8")
    depth, quoted, escaped = 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > 64:
                raise ValueError("JSON_DEPTH_LIMIT")
        elif char in "]}":
            depth -= 1
    return DECODER.decode(text)


def extract_response(raw: bytes) -> tuple[bytes, dict]:
    """Use decoder token spans, never regex or re-serialization of raw JSON."""
    obj = strict(raw, MAX_BYTES + 32_000)
    if not isinstance(obj, dict) or set(obj) != {"description", "prescription"}:
        raise ValueError("ENVELOPE_FIELDS")
    if not isinstance(obj["description"], str) or not isinstance(obj["prescription"], dict):
        raise ValueError("ENVELOPE_TYPES")
    text = raw.decode("utf-8")

    def skip(pos):
        while pos < len(text) and text[pos] in " \t\r\n":
            pos += 1
        return pos

    pos = skip(0) + 1
    while True:
        pos = skip(pos)
        key, pos = DECODER.raw_decode(text, pos)
        pos = skip(pos)
        if text[pos] != ":":
            raise ValueError("ENVELOPE_COLON")
        start = skip(pos + 1)
        _, end = DECODER.raw_decode(text, start)
        if key == "prescription":
            byte_start = len(text[:start].encode("utf-8"))
            byte_end = len(text[:end].encode("utf-8"))
            fragment = raw[byte_start:byte_end]
            if len(fragment) > MAX_BYTES:
                raise ValueError("JSON_SIZE_LIMIT")
            return fragment, {"response_sha256": digest(raw), "start_byte": byte_start,
                              "end_byte": byte_end, "description": obj["description"]}
        pos = skip(end) + 1


def save(path: Path, value: object) -> None:
    """Exclusive evidence creation; do not silently overwrite existing facts."""
    raw = canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def read_verified(path: Path, expected: str) -> object:
    if path.is_symlink() or not path.is_file():
        raise ValueError("REGULAR_EVIDENCE_REQUIRED")
    raw = path.read_bytes()
    if digest(raw) != expected:
        raise ValueError("EVIDENCE_HASH_MISMATCH")
    return strict(raw, max(MAX_BYTES, len(raw)))


def store_artifact(root: Path, raw: bytes, task_hash: str) -> tuple[Path, dict]:
    obj = strict(raw)
    if not isinstance(obj, dict):
        raise ValueError("PRESCRIPTION_OBJECT_REQUIRED")
    body = canonical(obj)
    if strict(body) != obj:
        raise ValueError("CANONICAL_VALUE_CHANGED")
    identity = {"task_contract_hash": task_hash, "schema_id": "optical-design-artifact/v1",
                "canonicalization_version": CANONICALIZATION,
                "canonical_artifact_sha256": digest(body)}
    artifact_id = digest(canonical(identity))
    directory = root / artifact_id
    if directory.exists():
        existing = load_artifact(directory, task_hash)
        if existing != identity:
            raise ValueError("ARTIFACT_CONFLICT")
    else:
        directory.mkdir(parents=True)
        with (directory / "prescription.json").open("xb") as stream:
            stream.write(body)
        save(directory / "artifact.json", identity)
    return directory, identity


def load_artifact(directory: Path, task_hash: str) -> dict:
    if directory.is_symlink() or (directory / "artifact.json").is_symlink():
        raise ValueError("REGULAR_ARTIFACT_REQUIRED")
    identity = strict((directory / "artifact.json").read_bytes())
    if set(identity) != {"task_contract_hash", "schema_id", "canonicalization_version", "canonical_artifact_sha256"} or identity["schema_id"] != "optical-design-artifact/v1":
        raise ValueError("ARTIFACT_SCHEMA_MISMATCH")
    if identity.get("task_contract_hash") != task_hash:
        raise ValueError("TASK_IDENTITY_MISMATCH")
    if identity.get("canonicalization_version") != CANONICALIZATION:
        raise ValueError("CANONICALIZATION_MISMATCH")
    if directory.name != digest(canonical(identity)):
        raise ValueError("ARTIFACT_IDENTITY_MISMATCH")
    value = read_verified(directory / "prescription.json", identity["canonical_artifact_sha256"])
    if canonical(value) != (directory / "prescription.json").read_bytes():
        raise ValueError("NONCANONICAL_ARTIFACT")
    return identity
