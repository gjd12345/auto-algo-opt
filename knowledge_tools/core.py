"""Core functions for the offline optimisation knowledge base.

Only the standard library is required.  PyYAML is optional and is used only
with safe_load when parsing historical YAML records; content is never
executed.
"""

from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from . import CLASSIFICATION_VERSION, SCHEMA_VERSION, __version__
from .dashboard import dashboard_html

HEX64 = re.compile(r"^[0-9a-f]{64}$")
SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
ALLOWED_ENTRY_TYPES = {
    "problem", "method", "implementation", "evidence", "framework",
    "literature", "pending", "source",
}
ALLOWED_CATEGORIES = {
    "problem", "method", "implementation", "evidence", "framework",
    "literature", "pending", "supporting_evidence", "infrastructure",
    "generated_artifact", "optimization_frameworks_experiments",
}
ALLOWED_ROLES = {
    "code", "experiment_config", "data", "evaluation_result", "report",
    "literature", "infrastructure", "generated_artifact", "unknown",
}

# A path may have a problem-family signal while still being classified as a
# framework/search artifact by role.  This keeps search control separate from
# problem heuristics.
FAMILY_INFO: dict[str, dict[str, Any]] = {
    "online_bin_packing": {
        "label": "Online bin packing (OBP)",
        "aliases": ["obp", "bp_online", "bin_packing_online", "online_bin_packing", "装箱", "在线装箱"],
        "online_offline": "online",
        "form": "one-dimensional items arrive sequentially; placement into fixed-capacity bins is irrevocable",
    },
    "offline_bin_packing": {
        "label": "Offline bin packing (BP)",
        "aliases": ["bin_packing", "bin-packing", "offline_bin_packing", "离线装箱"],
        "online_offline": "offline",
        "form": "one-dimensional item sizes are known before assigning items to minimum-capacity bins",
    },
    "tsp": {
        "label": "Traveling salesman problem (TSP)",
        "aliases": ["tsp", "traveling_salesman", "travelling_salesman", "旅行商"],
        "online_offline": "offline",
        "form": "a minimum-cost Hamiltonian cycle, with metric or asymmetric assumptions recorded per implementation",
    },
    "cvrp": {
        "label": "Capacitated vehicle routing (CVRP)",
        "aliases": ["cvrp", "vehicle_routing", "vehicle-routing", "车辆路径"],
        "online_offline": "offline",
        "form": "depot-to-customer routes cover each customer once without exceeding vehicle capacity",
    },
    "knapsack": {
        "label": "Knapsack",
        "aliases": ["knapsack", "背包"],
        "online_offline": "offline",
        "form": "choose items under a capacity or budget constraint to maximise value",
    },
    "mixer_split": {
        "label": "Mixer split",
        "aliases": ["mixer_split", "mixer-split"],
        "online_offline": "unknown",
        "form": "repository-specific mixer split problem; formal contract remains to be read",
    },
    "insertships_routing": {
        "label": "Insertships routing",
        "aliases": ["insertships", "insert_ships", "insert-ships"],
        "online_offline": "unknown",
        "form": "repository-specific ship insertion/routing problem; formal contract remains to be read",
    },
}


FRAMEWORK_PATH_MARKERS = (
    "eoh_rag/",
    "/search_control/",
    "search_controller",
    "search-control",
    "strategy_router",
    "rag_context",
    "cross_problem",
    "cross-problem",
    "/memory.py",
    "/memory/",
    "agent_controller",
    "/prompts/",
    "eoh_rag_workspace/experiments",
    "eoh_rag_workspace/strategies",
    "/selector/",
    "/feedback/",
)
FRAMEWORK_EXCLUDE_MARKERS = (
    "official_eoh/examples/",
    "/problems/",
)
RUN_TERMS = (
    "run", "result", "summary", "report", "manifest", "protocol",
    "evaluation", "outcome", "index", "batch", "experiment", "calibration",
    "结果", "协议",
)
RUN_DIRECTORIES = (
    "/runs/", "/results/", "/reports/", "/experiments/", "/evidence/",
    "/结果/", "/协议/", "/运行状态/",
)
SOURCE_READ_DEPTHS = frozenset({"metadata", "metadata_only", "abstract", "full_text_local"})
EVALUATION_EVIDENCE_PREFIXES = ("evaluation:", "metric:")
GENERIC_RUN_INDEX = "run-index:inventory"


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _git(repo: Path, args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def resolve_commit(repo: Path, ref: str) -> str:
    """Resolve a ref to a commit without changing the working tree."""
    result = _git(repo, ["rev-parse", "--verify", f"{ref}^{{commit}}"])
    return result.stdout.decode("ascii", "strict").strip()


def list_git_blobs(repo: Path, commit: str) -> list[dict[str, str]]:
    """Return every tracked blob in a commit using raw Git object paths."""
    result = _git(
        repo,
        ["-c", "core.quotePath=false", "ls-tree", "-r", "-z", "--full-tree", commit],
    )
    blobs: list[dict[str, str]] = []
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        try:
            header, raw_path = record.split(b"\t", 1)
            mode, kind, object_id = header.split(b" ", 2)
        except ValueError:
            continue
        if kind != b"blob":
            continue
        path = raw_path.decode("utf-8", "surrogateescape").replace("\\", "/")
        blobs.append({"path": path, "git_blob": object_id.decode("ascii"), "mode": mode.decode("ascii")})
    return blobs


def git_blob_bytes(repo: Path, commit: str, path: str) -> bytes:
    # Reading an object with show does not checkout or write it.
    return _git(repo, ["show", f"{commit}:{path}"]).stdout


def _normalised_name(path: str) -> str:
    return path.replace("\\", "/").casefold()


def _path_tokens(path: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", _normalised_name(path)) if token}


def _family_scores(path: str, text: str = "") -> dict[str, int]:
    name = _normalised_name(path)
    tokens = _path_tokens(path)
    preview = text.casefold()[:12000]
    scores: dict[str, int] = {}
    for family, info in FAMILY_INFO.items():
        score = 0
        for alias in info["aliases"]:
            alias_norm = alias.casefold()
            if alias_norm in name:
                score += 5 if "_" in alias_norm or "-" in alias_norm else 4
            if alias_norm.replace("_", " ") in preview:
                score += 1
        if family == "cvrp" and ("vehicle routing" in preview or "vehicle-routing" in preview):
            score += 2
        if family == "tsp" and "traveling salesman" in preview:
            score += 2
        if family == "online_bin_packing" and ("online bin" in preview or "on-line bin" in preview):
            score += 2
        if family == "offline_bin_packing" and "bin packing" in preview and "online" not in preview:
            score += 1
        if family == "insertships_routing" and ("insertships" in tokens or "insert ships" in preview):
            score += 4
        if score:
            scores[family] = score
    if "bp" in tokens:
        if tokens & {"offline", "ffd", "bfd"}:
            scores["offline_bin_packing"] = max(scores.get("offline_bin_packing", 0), 4)
        elif tokens & {"online", "obp", "hifo"}:
            scores["online_bin_packing"] = max(scores.get("online_bin_packing", 0), 5)
        else:
            scores["online_bin_packing"] = max(scores.get("online_bin_packing", 0), 3)
    if "solomon" in tokens or re.search(r"(?:^|/)rc\d{3}\.json$", name):
        scores["cvrp"] = max(scores.get("cvrp", 0), 5)
    return scores


def _framework_signal(path: str) -> bool:
    name = _normalised_name(path)
    if any(marker in name for marker in FRAMEWORK_EXCLUDE_MARKERS):
        return False
    return any(marker in name for marker in FRAMEWORK_PATH_MARKERS)


def classify_path(path: str, text: str = "") -> dict[str, Any]:
    """Classify a tracked path with explicit confidence and unknown states."""
    name = _normalised_name(path)
    suffix = PurePosixPath(path).suffix.casefold()
    scores = _family_scores(path, text)
    family = max(scores, key=scores.get) if scores else "unknown"
    top_score = scores.get(family, 0)
    if top_score < 2:
        family = "unknown"
        top_score = 0
    confidence = "high" if top_score >= 5 else "medium" if top_score >= 2 else "low"

    if suffix in {".py", ".go", ".sh", ".js", ".ts", ".java", ".rs", ".cpp", ".c", ".h"}:
        role = "code"
    elif (
        suffix in {".csv", ".tsv", ".parquet", ".npz", ".npy", ".bin"}
        or "testdata" in name
        or "/data/" in name
        or "solomon" in name
        or re.search(r"(?:^|/)rc\d{3}\.json$", name)
    ):
        role = "data"
    elif suffix in {".pdf", ".bib"} or any(term in name for term in ("literature", "paper", "publication")):
        role = "literature"
    elif suffix in {".json", ".jsonl", ".yaml", ".yml", ".toml"} and any(term in name for term in ("manifest", "config", "schema", "contract", "profile")):
        role = "experiment_config"
    elif any(term in name for term in ("result", "report", "summary", "outcome", "evaluation", "evidence", "结果")):
        role = "evaluation_result" if suffix in {".json", ".jsonl", ".csv"} else "report"
    elif suffix in {".md", ".rst", ".txt", ".html"}:
        role = "report"
    elif any(term in name for term in (".github", "pyproject", "requirements", "docker", "makefile", "workflow")):
        role = "infrastructure"
    elif suffix in {".png", ".jpg", ".jpeg", ".drawio", ".svg"} or any(term in name for term in ("build", "dist", "generated")):
        role = "generated_artifact"
    else:
        role = "unknown"

    framework = _framework_signal(path)
    if framework:
        category = "optimization_frameworks_experiments"
    elif family != "unknown" and role == "code":
        category = "implementation"
    elif family != "unknown" and role == "evaluation_result":
        category = "evidence"
    elif family != "unknown" and role in {"data", "experiment_config", "report"}:
        category = "supporting_evidence"
    elif family != "unknown":
        category = "problem"
    elif role == "literature":
        category = "literature"
    elif role in {"infrastructure", "generated_artifact"}:
        category = role
    elif role in {"experiment_config", "evaluation_result", "report"}:
        category = "supporting_evidence"
    else:
        category = "pending"
    status = "classified" if family != "unknown" or category not in {"pending"} else "pending"
    info = FAMILY_INFO.get(family, {})
    return {
        "category": category,
        "problem_family": family,
        "online_offline": info.get("online_offline", "unknown"),
        "problem_form": info.get("form", ""),
        "role": role,
        "confidence": confidence,
        "classification_status": status,
        "classification_rule_version": CLASSIFICATION_VERSION,
        "framework_signal": framework,
    }


def _format_for_path(path: str) -> str:
    suffix = PurePosixPath(path).suffix.casefold()
    return {
        ".json": "json", ".jsonl": "jsonl", ".yaml": "yaml", ".yml": "yaml",
        ".csv": "csv", ".tsv": "tsv", ".md": "markdown", ".txt": "text",
        ".py": "python", ".go": "go", ".sh": "shell", ".html": "html",
        ".drawio": "drawio_xml", ".pdf": "pdf",
    }.get(suffix, suffix.lstrip(".") or "binary")


def _safe_text(data: bytes, limit: int | None = None) -> str:
    if limit is not None:
        data = data[:limit]
    return data.decode("utf-8", "replace")


def _is_headline_summary(path: str) -> bool:
    name = _normalised_name(path)
    return "605" in name and any(token in path for token in ("精英", "elite", "相似度", "similarity"))


def _is_run_candidate(path: str, role: str) -> bool:
    name = _normalised_name(path)
    suffix = PurePosixPath(path).suffix.casefold()
    if suffix not in {".json", ".jsonl", ".yaml", ".yml", ".csv", ".tsv"}:
        return False
    return (
        role in {"experiment_config", "evaluation_result"}
        or any(term in name for term in RUN_TERMS)
        or any(directory in f"/{name}/" for directory in RUN_DIRECTORIES)
        or _is_headline_summary(path)
    )


def _looks_like_run_value(value: Any) -> bool:
    if isinstance(value, Mapping):
        keys = {str(k).casefold() for k in value}
        return bool(keys & {
            "run_id", "runid", "status", "metrics", "objective", "result",
            "problem", "suite", "evaluations", "artifacts", "candidate",
        })
    return isinstance(value, list) and bool(value)


def _collect_referenced_paths(value: Any) -> list[str]:
    """Collect path-like fields without treating arbitrary IDs as files."""
    keys = {
        "path", "file", "file_path", "filepath", "artifact", "artifact_path",
        "report", "report_path", "result_path", "manifest_path", "code_path",
        "output_path", "source_path",
    }
    found: set[str] = set()

    def visit(node: Any) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                key_name = str(key).casefold().replace("-", "_")
                if key_name in keys and isinstance(child, str):
                    candidate = child.strip().replace("\\", "/")
                    if (
                        candidate
                        and not re.match(r"^(?:https?|git|file)://", candidate, re.I)
                        and ("/" in candidate or "." in PurePosixPath(candidate).name)
                    ):
                        found.add(_redact_external_reference(candidate.lstrip("./")))
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return sorted(found)


def _redact_external_reference(reference: str) -> str:
    """Keep a useful basename while excluding personal absolute paths."""
    if (
        re.match(r"^[A-Za-z]:/", reference)
        or reference.startswith("/")
        or reference.startswith("~")
    ):
        basename = PurePosixPath(reference).name or "unknown"
        return f"<external>/{basename}"
    return reference


def parse_run_container(
    path: str,
    data: bytes,
    classification: Mapping[str, Any],
    *,
    max_bytes: int = 8 * 1024 * 1024,
) -> dict[str, Any]:
    """Safely parse one historical run container.

    This returns parser observations only.  It never claims that a run was
    independent or that a score is valid; such claims require evidence links.
    """
    suffix = PurePosixPath(path).suffix.casefold()
    base: dict[str, Any] = {
        "path": path,
        "format": _format_for_path(path),
        "problem_family": classification.get("problem_family", "unknown"),
        "status": "unsupported",
        "record_count": 0,
        "duplicate_of": None,
        "independence": "unknown",
        "notes": [],
        "referenced_paths": [],
    }
    name = _normalised_name(path)
    if _is_headline_summary(path):
        base["independence"] = "summary_clue"
        base["notes"].append("headline 605-style summary; treat as a clue to original records, not an independent experiment")
    elif any(term in name for term in ("shared_pool", "shared-pool", "inherited_pool", "snapshot")):
        base["independence"] = "derived_or_shared"
        base["notes"].append("path suggests a shared pool or snapshot; not counted as an independent experiment")
    elif any(term in name for term in ("resume", "continu", "retry", "replic", "rerun", "续跑")):
        base["independence"] = "derived_or_repeat"
        base["notes"].append("path suggests a continuation, retry, or replicate; verify before counting")

    if len(data) > max_bytes:
        base["status"] = "unsupported_large"
        base["notes"].append(f"parser capped at {max_bytes} bytes; content hash still covers the full object")
        return base
    parsed_payload: Any = None
    try:
        if suffix == ".json":
            value = json.loads(data.decode("utf-8"))
            parsed_payload = value
            base["record_count"] = len(value) if isinstance(value, list) else 1
            base["status"] = "parsed" if _looks_like_run_value(value) else "parsed_non_run_json"
            if base["status"] != "parsed":
                base["notes"].append("valid JSON was found but no run-like fields were recognised")
            base["content_digest"] = sha256_bytes(canonical_json(value))
            if isinstance(value, Mapping):
                for key in ("run_id", "runId", "id", "status", "suite", "problem", "objective"):
                    if key in value and isinstance(value[key], (str, int, float, bool)):
                        if key == "status":
                            output_key = "record_status"
                        else:
                            output_key = "run_id" if key == "runId" else key
                        base[output_key] = value[key]
        elif suffix == ".jsonl":
            records = []
            bad_lines = []
            for line_no, line in enumerate(data.decode("utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except (ValueError, UnicodeError):
                    bad_lines.append(line_no)
            base["record_count"] = len(records)
            parsed_payload = records
            base["status"] = "parsed" if records and not bad_lines else "partial" if records else "corrupt"
            if bad_lines:
                base["notes"].append(f"invalid JSONL lines: {bad_lines[:20]}")
            base["content_digest"] = sha256_bytes(canonical_json(records))
        elif suffix in {".yaml", ".yml"}:
            try:
                import yaml  # type: ignore
            except ImportError:
                base["status"] = "unsupported_yaml_dependency"
                base["notes"].append("PyYAML is not installed; no YAML code was executed")
                return base
            try:
                value = yaml.safe_load(data.decode("utf-8"))
            except Exception as exc:
                # PyYAML uses YAMLError (which is not a ValueError) for
                # malformed documents.  Preserve the discovery record rather
                # than allowing one bad historical file to abort inventory.
                base["status"] = "corrupt"
                base["notes"].append(f"parser error: {type(exc).__name__}: {exc}")
                return base
            parsed_payload = value
            base["record_count"] = len(value) if isinstance(value, list) else 1
            base["status"] = "parsed" if _looks_like_run_value(value) else "parsed_non_run_yaml"
            base["content_digest"] = sha256_bytes(canonical_json(value))
        elif suffix in {".csv", ".tsv"}:
            delimiter = "\t" if suffix == ".tsv" else ","
            rows = list(csv.DictReader(data.decode("utf-8-sig").splitlines(), delimiter=delimiter))
            parsed_payload = rows
            base["record_count"] = len(rows)
            headers = [str(h).casefold() for h in (rows[0].keys() if rows else [])]
            looks_like = rows and any(
                any(term in header for term in ("run", "objective", "metric", "problem", "status", "score"))
                for header in headers
            )
            base["status"] = "parsed" if looks_like else "parsed_non_run_csv"
            base["content_digest"] = sha256_bytes(canonical_json(rows))
    except (ValueError, UnicodeError, csv.Error, TypeError) as exc:
        base["status"] = "corrupt"
        base["notes"].append(f"parser error: {type(exc).__name__}: {exc}")
    if parsed_payload is not None:
        base["referenced_paths"] = _collect_referenced_paths(parsed_payload)
    return base


def inventory_repository(repo: Path, ref: str) -> dict[str, Any]:
    repo = repo.resolve()
    commit = resolve_commit(repo, ref)
    blobs = list_git_blobs(repo, commit)
    files: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
    digest_to_run_path: dict[str, str] = {}
    problem_families: set[str] = set()
    for blob in blobs:
        path = blob["path"]
        raw = git_blob_bytes(repo, commit, path)
        preview_formats = {
            "python", "go", "shell", "markdown", "text", "json", "jsonl",
            "yaml", "csv", "tsv", "html",
        }
        preview = _safe_text(raw, 12000) if _format_for_path(path) in preview_formats else ""
        classification = classify_path(path, preview)
        family = classification["problem_family"]
        if family != "unknown":
            problem_families.add(family)
        file_record = {
            **blob,
            "size": len(raw),
            "sha256": sha256_bytes(raw),
            "format": _format_for_path(path),
            **classification,
        }
        if _is_run_candidate(path, classification["role"]):
            run = parse_run_container(path, raw, classification)
            digest = run.get("content_digest")
            if digest and digest in digest_to_run_path:
                run["status"] = "duplicate"
                run["duplicate_of"] = digest_to_run_path[digest]
                run["notes"].append("same canonical parsed content as an earlier container")
            elif digest:
                digest_to_run_path[digest] = path
            run["content_sha256"] = file_record["sha256"]
            runs.append(run)
            file_record["run_parse_status"] = run["status"]
        else:
            file_record["run_parse_status"] = "not_applicable"
        files.append(file_record)

    tracked_paths = {record["path"] for record in files}
    tracked_basenames: dict[str, list[str]] = {}
    for tracked_path in tracked_paths:
        tracked_basenames.setdefault(PurePosixPath(tracked_path).name, []).append(tracked_path)
    for run in runs:
        missing = []
        for reference in run.get("referenced_paths", []):
            candidate = str(reference).replace("\\", "/").lstrip("./")
            if candidate in tracked_paths:
                continue
            basename_matches = tracked_basenames.get(PurePosixPath(candidate).name, [])
            if basename_matches:
                run.setdefault("notes", []).append(
                    f"reference {reference!r} matched by basename: {basename_matches[:3]}"
                )
            else:
                missing.append(reference)
        if missing:
            run["missing_references"] = sorted(set(missing))
            if run.get("status") in {"parsed", "parsed_non_run_json", "parsed_non_run_yaml", "parsed_non_run_csv"}:
                run["parse_status"] = run["status"]
                run["status"] = "missing"
    run_status_by_path = {run["path"]: run["status"] for run in runs}
    for record in files:
        if record["path"] in run_status_by_path:
            record["run_parse_status"] = run_status_by_path[record["path"]]

    role_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    format_counts: dict[str, int] = {}
    pending = []
    for record in files:
        for counter, key in (
            (role_counts, "role"), (category_counts, "category"),
            (format_counts, "format"),
        ):
            value = str(record[key])
            counter[value] = counter.get(value, 0) + 1
        if record["classification_status"] == "pending":
            pending.append(record["path"])
    return {
        "schema_version": SCHEMA_VERSION,
        "tool_version": __version__,
        "classification_rule_version": CLASSIFICATION_VERSION,
        "generated_at": utc_now(),
        "repository": repo.name,
        "repository_path_policy": "absolute local path omitted from published inventory",
        "ref_requested": ref,
        "ref_resolved": commit,
        "source_main_sha": commit,
        "tracked_file_count": len(files),
        "files": files,
        "runs": runs,
        "problem_families": sorted(problem_families),
        "counts": {"roles": role_counts, "categories": category_counts, "formats": format_counts},
        "coverage": {
            "inventory_complete": True,
            "tracked_files": len(files),
            "classified_files": len(files) - len(pending),
            "pending_classification_files": len(pending),
            "classification_coverage": round((len(files) - len(pending)) / len(files), 6) if files else 1.0,
            "high_confidence_classified": sum(item.get("confidence") == "high" for item in files),
            "high_confidence_coverage": round(
                sum(item.get("confidence") == "high" for item in files) / len(files), 6
            ) if files else 1.0,
            "deep_read_coverage": None,
            "evidence_association_coverage": None,
        },
        "pending_classification": pending,
        "run_summary": {
            "containers_discovered": len(runs),
            "parsed": sum(r["status"] == "parsed" for r in runs),
            "duplicates": sum(r["status"] == "duplicate" for r in runs),
            "missing": sum(r["status"] == "missing" or bool(r.get("missing_references")) for r in runs),
            "corrupt_or_partial": sum(r["status"] in {"corrupt", "partial"} for r in runs),
            "unsupported": sum(str(r["status"]).startswith("unsupported") for r in runs),
            "independence_requires_manual_review": sum(r["independence"] != "unknown" for r in runs),
            "summary_clue": sum(r.get("independence") == "summary_clue" for r in runs),
        },
        "notes": [
            "All file records come from Git objects at ref_resolved; the working tree was not checked out.",
            "A complete inventory does not imply deep reading or validated algorithm evidence.",
            "Run summaries are parser observations. Shared pools, continuations, retries and replicas are not counted as independent experiments.",
        ],
    }


def inventory_markdown(inventory: Mapping[str, Any]) -> str:
    counts = inventory.get("counts", {})
    coverage = inventory.get("coverage", {})
    lines = [
        "# main 全量盘点",
        "",
        f"- source commit: {inventory.get('source_main_sha')}",
        f"- requested ref: {inventory.get('ref_requested')}",
        f"- tracked files: **{inventory.get('tracked_file_count', 0)}**",
        f"- classification coverage: **{coverage.get('classification_coverage', 0):.1%}**",
        f"- high-confidence coverage: **{coverage.get('high_confidence_coverage', 0):.1%}**",
        "- deep-read coverage: not inferred from inventory",
        "",
        "## 角色计数",
        "",
    ]
    for key, value in sorted(counts.get("roles", {}).items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## 分类计数", ""])
    for key, value in sorted(counts.get("categories", {}).items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## 运行容器解析", ""])
    for key, value in inventory.get("run_summary", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## 问题族", ""])
    for family in inventory.get("problem_families", []):
        label = FAMILY_INFO.get(family, {}).get("label", family)
        lines.append(f"- {family} — {label}")
    pending = inventory.get("pending_classification", [])
    lines.extend([
        "", "## 待分类", "",
        f"共 {len(pending)} 个文件；完整路径见 inventory.json 的 pending_classification。",
        "",
    ])
    return "\n".join(lines)


def _classification_markdown(inventory: Mapping[str, Any], classification: Mapping[str, Any]) -> str:
    files = inventory.get("files", [])
    lines = [
        "# 全量分类表",
        "",
        f"- source commit: {classification.get('source_main_sha')}",
        f"- tracked files: {classification.get('tracked_file_count', 0)}",
        f"- pending: {len(classification.get('pending', []))}",
        f"- high-confidence: {inventory.get('coverage', {}).get('high_confidence_classified', 0)}",
        "",
        "不确定项不作猜测性归类。下面按问题族列出角色分布、低置信抽样和待分类全清单。",
        "",
    ]
    by_family: dict[str, list[Mapping[str, Any]]] = {}
    for item in files:
        if not isinstance(item, Mapping):
            continue
        by_family.setdefault(str(item.get("problem_family") or "unknown"), []).append(item)
    for family in sorted(by_family):
        rows = by_family[family]
        lines.append(f"## {family} — {FAMILY_INFO.get(family, {}).get('label', family)}")
        lines.append("")
        role_counts: dict[str, int] = {}
        category_counts: dict[str, int] = {}
        for item in rows:
            role_counts[str(item.get("role"))] = role_counts.get(str(item.get("role")), 0) + 1
            category_counts[str(item.get("category"))] = category_counts.get(str(item.get("category")), 0) + 1
        lines.append(
            "- 角色：" + ", ".join(f"{key} {value}" for key, value in sorted(role_counts.items()))
        )
        lines.append(
            "- 类别：" + ", ".join(f"{key} {value}" for key, value in sorted(category_counts.items()))
        )
        low = [item for item in rows if item.get("confidence") == "low"][:20]
        if low:
            lines.append("- 低置信抽样：")
            for item in low:
                lines.append(
                    f"  - `{item.get('path')}` · {item.get('role')} · {item.get('category')}"
                )
        lines.append("")
    pending = classification.get("pending", [])
    lines.extend(["## 待分类全清单", ""])
    for path in pending:
        lines.append(f"- `{path}`")
    if not pending:
        lines.append("- （无）")
    lines.append("")
    return "\n".join(lines)


def write_inventory(out: Path, inventory: Mapping[str, Any]) -> tuple[Path, Path]:
    """Write JSON and Markdown, accepting either a directory or a JSON path."""
    if out.suffix.casefold() == ".json":
        json_path = out
        markdown_path = out.with_suffix(".md")
    else:
        out.mkdir(parents=True, exist_ok=True)
        json_path = out / "inventory.json"
        markdown_path = out / "inventory.md"
    write_json(json_path, inventory)
    classification = {
        "schema_version": SCHEMA_VERSION,
        "classification_rule_version": CLASSIFICATION_VERSION,
        "source_main_sha": inventory.get("source_main_sha"),
        "tracked_file_count": inventory.get("tracked_file_count"),
        "files": [
            {
                "path": item.get("path"),
                "role": item.get("role"),
                "category": item.get("category"),
                "problem_family": item.get("problem_family"),
                "online_offline": item.get("online_offline"),
                "confidence": item.get("confidence"),
                "classification_status": item.get("classification_status"),
                "run_parse_status": item.get("run_parse_status"),
            }
            for item in inventory.get("files", [])
        ],
        "pending": inventory.get("pending_classification", []),
        "problem_families": inventory.get("problem_families", []),
    }
    write_json(json_path.parent / "classification.json", classification)
    (json_path.parent / "classification.md").write_text(
        _classification_markdown(inventory, classification),
        encoding="utf-8",
        newline="\n",
    )
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(inventory_markdown(inventory), encoding="utf-8", newline="\n")
    return json_path, markdown_path


def _entry_files(workspace: Path) -> list[tuple[Path, Path]]:
    entries = workspace / "entries"
    if not entries.is_dir():
        return []
    result = []
    for metadata in sorted(entries.glob("*.json")):
        if not metadata.name.startswith("."):
            result.append((metadata, metadata.with_suffix(".md")))
    return result


def _required_sections(markdown: str) -> list[str]:
    return [
        "## 定义或方法步骤",
        "## 适用条件、假设与限制",
        "## 来源及支持的具体结论",
        "## 代码和评测关联",
        "## 未确认项与冲突证据",
    ]


def _substantive_evidence_refs(refs: Any) -> list[str]:
    if not isinstance(refs, list):
        return []
    result = []
    for item in refs:
        text = str(item).strip()
        if text and text != GENERIC_RUN_INDEX and not text.startswith("run-index:"):
            result.append(text)
    return result


def _locatable_evaluation_refs(
    refs: Any,
    *,
    inventory_paths: set[str],
    entry_ids: set[str],
) -> list[str]:
    """evaluation:/metric: refs that name an existing file or entry and bind suite/metric/budget."""
    found: list[str] = []
    for item in refs if isinstance(refs, list) else []:
        text = str(item).strip()
        if not text.startswith(EVALUATION_EVIDENCE_PREFIXES):
            continue
        payload = text.split(":", 1)[1]
        parts = [part.strip() for part in payload.split(";") if part.strip()]
        if not parts:
            continue
        target = parts[0]
        flags = {}
        for part in parts[1:]:
            if "=" in part:
                key, value = part.split("=", 1)
                flags[key.strip()] = value.strip()
        if target not in inventory_paths and target not in entry_ids:
            continue
        if not all(flags.get(key) for key in ("suite", "metric", "budget")):
            continue
        found.append(text)
    return found


def _metadata_has_evidence(path: Path) -> bool:
    try:
        value = read_json(path)
        return isinstance(value, Mapping) and bool(_substantive_evidence_refs(value.get("evidence_refs")))
    except Exception:
        return False


def validate_workspace(workspace: Path) -> dict[str, Any]:
    workspace = workspace.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    inventory_path = workspace / "inventory.json"
    sources_path = workspace / "sources.json"
    taxonomy_path = workspace / "taxonomy.json"
    try:
        inventory = read_json(inventory_path)
    except FileNotFoundError:
        inventory = {}
        errors.append("missing inventory.json")
    except (ValueError, UnicodeError) as exc:
        inventory = {}
        errors.append(f"invalid inventory.json: {exc}")
    try:
        source_doc = read_json(sources_path)
    except FileNotFoundError:
        source_doc = {}
        errors.append("missing sources.json")
    except (ValueError, UnicodeError) as exc:
        source_doc = {}
        errors.append(f"invalid sources.json: {exc}")
    try:
        taxonomy = read_json(taxonomy_path)
    except FileNotFoundError:
        taxonomy = {}
        warnings.append("missing taxonomy.json; build will generate a default taxonomy")
    except (ValueError, UnicodeError) as exc:
        taxonomy = {}
        errors.append(f"invalid taxonomy.json: {exc}")

    files = inventory.get("files", []) if isinstance(inventory, Mapping) else []
    file_by_path = {
        str(item.get("path")): item for item in files if isinstance(item, Mapping)
    }
    if inventory and inventory.get("tracked_file_count") != len(files):
        errors.append("inventory tracked_file_count does not match files length")
    for item in files:
        path = item.get("path")
        digest = item.get("sha256")
        if not path or not isinstance(path, str):
            errors.append("inventory file has no path")
        if not isinstance(digest, str) or not HEX64.match(digest):
            errors.append(f"invalid file sha256 for {path!r}")
        if item.get("role") not in ALLOWED_ROLES:
            errors.append(f"unknown role for {path!r}: {item.get('role')!r}")
        if item.get("classification_rule_version") != CLASSIFICATION_VERSION:
            errors.append(f"classification rule mismatch for {path!r}")
        if item.get("classification_status") not in {"classified", "pending"}:
            errors.append(f"invalid classification status for {path!r}")
        if item.get("online_offline") not in {"online", "offline", "unknown"}:
            errors.append(f"invalid online/offline value for {path!r}")

    sources = source_doc.get("sources", []) if isinstance(source_doc, Mapping) else []
    source_by_id: dict[str, Mapping[str, Any]] = {}
    for source in sources:
        if not isinstance(source, Mapping):
            errors.append("source entry is not an object")
            continue
        source_id = source.get("id")
        if not isinstance(source_id, str) or not SLUG.match(source_id):
            errors.append(f"invalid source id: {source_id!r}")
        elif source_id in source_by_id:
            errors.append(f"duplicate source id: {source_id}")
        else:
            source_by_id[source_id] = source
        url = source.get("url")
        if not isinstance(url, str) or not re.match(r"^https?://", url):
            errors.append(f"source {source_id!r} has no http(s) URL")
        if not source.get("title") or not source.get("authors") or not source.get("year"):
            errors.append(f"source {source_id!r} missing title/authors/year")
        if source.get("selected") and not source.get("selection_reason"):
            errors.append(f"selected source {source_id!r} needs selection_reason")
        depth = source.get("read_depth")
        if depth not in SOURCE_READ_DEPTHS:
            errors.append(f"source {source_id!r} read_depth must be one of {sorted(SOURCE_READ_DEPTHS)}")

    metadata_count = 0
    method_code_owners: dict[str, str] = {}
    entry_ids: set[str] = set()
    for metadata_path, markdown_path in _entry_files(workspace):
        try:
            early = read_json(metadata_path)
        except (FileNotFoundError, ValueError, UnicodeError):
            continue
        if isinstance(early, Mapping) and isinstance(early.get("id"), str):
            entry_ids.add(early["id"])
    inventory_paths = {str(item.get("path")) for item in files if isinstance(item, Mapping)}
    for metadata_path, markdown_path in _entry_files(workspace):
        metadata_count += 1
        try:
            metadata = read_json(metadata_path)
        except (FileNotFoundError, ValueError, UnicodeError) as exc:
            errors.append(f"invalid metadata {metadata_path.name}: {exc}")
            continue
        if not isinstance(metadata, Mapping):
            errors.append(f"metadata {metadata_path.name} is not an object")
            continue
        entry_id = metadata.get("id")
        if not isinstance(entry_id, str) or not SLUG.match(entry_id):
            errors.append(f"invalid entry id in {metadata_path.name}: {entry_id!r}")
        if metadata_path.stem != entry_id:
            errors.append(f"metadata filename/id mismatch: {metadata_path.name}")
        if metadata.get("type") not in ALLOWED_ENTRY_TYPES:
            errors.append(f"unknown entry type for {entry_id!r}: {metadata.get('type')!r}")
        if metadata.get("category") not in ALLOWED_CATEGORIES:
            errors.append(f"unknown category for {entry_id!r}: {metadata.get('category')!r}")
        family = metadata.get("problem_family", "unknown")
        if family != "unknown" and family not in FAMILY_INFO:
            errors.append(f"unknown problem family for {entry_id!r}: {family!r}")
        for field in ("title", "category", "source_refs", "evidence_refs"):
            if field not in metadata:
                errors.append(f"entry {entry_id!r} missing {field}")
        source_refs = metadata.get("source_refs", [])
        if not isinstance(source_refs, list):
            errors.append(f"entry {entry_id!r} source_refs is not a list")
        else:
            for source_id in source_refs:
                if source_id not in source_by_id:
                    errors.append(f"entry {entry_id!r} references missing source {source_id!r}")
        evidence_refs = metadata.get("evidence_refs", [])
        if not isinstance(evidence_refs, list):
            errors.append(f"entry {entry_id!r} evidence_refs is not a list")
        elif any(not isinstance(ref, str) or not ref.strip() for ref in evidence_refs):
            errors.append(f"entry {entry_id!r} has malformed evidence_refs")
        elif any(str(ref).strip() == GENERIC_RUN_INDEX or str(ref).startswith("run-index:") for ref in evidence_refs):
            errors.append(f"entry {entry_id!r} uses generic run-index evidence; bind suite/metric/budget or use gap:")
        if not markdown_path.exists():
            errors.append(f"missing Markdown body for {entry_id!r}")
            continue
        markdown = markdown_path.read_text(encoding="utf-8")
        body_hash = sha256_file(markdown_path)
        if metadata.get("content_sha256") != body_hash:
            errors.append(f"content_sha256 mismatch for {entry_id!r}")
        for section in _required_sections(markdown):
            if section not in markdown:
                errors.append(f"entry {entry_id!r} missing required section {section}")
        eoh = (metadata.get("attributes") or {}).get("eoh_map") or {}
        if metadata.get("type") == "method" and isinstance(eoh, Mapping) and eoh.get("status") == "possible":
            if "## EoH 适配" not in markdown:
                errors.append(f"entry {entry_id!r} has eoh_map=possible but no ## EoH 适配")
            if eoh.get("adapter_kind") == "not_mappable":
                errors.append(f"entry {entry_id!r} possible map cannot use not_mappable adapter")
        for ref in metadata.get("code_refs", []) or []:
            if not isinstance(ref, Mapping):
                errors.append(f"entry {entry_id!r} has malformed code_ref")
                continue
            code_path = ref.get("path")
            if code_path not in file_by_path:
                errors.append(f"entry {entry_id!r} references code path absent from inventory: {code_path!r}")
            declared = ref.get("sha256")
            actual = file_by_path.get(code_path, {}).get("sha256")
            if declared and actual and declared != actual:
                errors.append(f"code hash mismatch for {entry_id!r}: {code_path}")
            if metadata.get("type") == "method" and isinstance(declared, str) and HEX64.match(declared):
                owner = method_code_owners.get(declared)
                if owner and owner != entry_id:
                    errors.append(
                        f"code hash {declared} is used as a representative implementation by both {owner!r} and {entry_id!r}"
                    )
                else:
                    method_code_owners[declared] = str(entry_id)
        relations = metadata.get("relations") or {}
        if relations and not isinstance(relations, Mapping):
            errors.append(f"entry {entry_id!r} relations is not an object")
        elif isinstance(relations, Mapping):
            for rel_key, rel_ids in relations.items():
                if not isinstance(rel_ids, list):
                    errors.append(f"entry {entry_id!r} relations.{rel_key} is not a list")
                    continue
                for rel_id in rel_ids:
                    if not isinstance(rel_id, str) or not rel_id.strip():
                        errors.append(f"entry {entry_id!r} has empty relations.{rel_key} id")
                        continue
                    if rel_key in {"problems", "methods", "implementations"}:
                        if rel_id not in entry_ids:
                            errors.append(f"entry {entry_id!r} relations.{rel_key} missing entry {rel_id!r}")
                    elif rel_key == "sources" or str(rel_id).startswith("src-"):
                        if rel_id not in source_by_id:
                            errors.append(f"entry {entry_id!r} relations.{rel_key} missing source {rel_id!r}")
        locatable_eval = _locatable_evaluation_refs(
            evidence_refs, inventory_paths=inventory_paths, entry_ids=entry_ids,
        )
        if metadata.get("status") == "validated" and not locatable_eval:
            errors.append(
                f"validated entry {entry_id!r} needs locatable evaluation evidence "
                "of the form evaluation:<inventory-path-or-entry>;suite=...;metric=...;budget=..."
            )
        if metadata.get("status") in {"pending", "unread"}:
            warnings.append(f"entry {entry_id!r} remains {metadata.get('status')}")

    entries_dir = workspace / "entries"
    if entries_dir.is_dir():
        for orphan in sorted(entries_dir.glob("*.md")):
            if not (entries_dir / f"{orphan.stem}.json").exists():
                errors.append(f"orphan Markdown body without metadata sidecar: {orphan.name}")

    if not metadata_count:
        errors.append("no entries found under entries/")
    return {
        "schema_version": SCHEMA_VERSION,
        "workspace": str(workspace),
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "entry_count": metadata_count,
        "source_count": len(source_by_id),
        "inventory_file_count": len(file_by_path),
        "source_main_sha": inventory.get("source_main_sha"),
        "coverage": {
            "inventoried": bool(inventory.get("coverage", {}).get("inventory_complete")),
            "classified": inventory.get("coverage", {}).get("classification_coverage"),
            "deep_read": sum(
                1 for item in sources
                if isinstance(item, Mapping) and item.get("read_depth") == "full_text_local"
            ),
            "abstract_read": sum(
                1 for item in sources
                if isinstance(item, Mapping) and item.get("read_depth") == "abstract"
            ),
            "evidence_associated_entries": sum(
                1 for metadata_path, _ in _entry_files(workspace)
                if _metadata_has_evidence(metadata_path)
            ),
        },
        "taxonomy": taxonomy,
    }


def _summary_from_markdown(markdown: str, limit: int = 280) -> str:
    in_code = False
    paragraphs: list[str] = []
    current: list[str] = []
    for line in markdown.splitlines():
        if line.strip().startswith(chr(96) * 3):
            in_code = not in_code
            continue
        if in_code:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-") or stripped.startswith("|"):
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        current.append(stripped)
    if current:
        paragraphs.append(" ".join(current))
    text = next((p for p in paragraphs if p), "")
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _default_taxonomy(inventory: Mapping[str, Any], entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    families = set(inventory.get("problem_families", []))
    for entry in entries:
        family = entry.get("problem_family")
        if family and family != "unknown":
            families.add(family)
    pages = []
    for family in sorted(families):
        info = FAMILY_INFO.get(family, {})
        pages.append({
            "id": family,
            "label": info.get("label", family),
            "kind": "problem_family",
            "form": info.get("form", "待补齐正式问题定义"),
            "online_offline": info.get("online_offline", "unknown"),
            "status": "classified" if family in FAMILY_INFO else "pending",
        })
    pages.extend([
        {"id": "optimization_frameworks_experiments", "label": "优化框架与实验策略", "kind": "framework", "status": "classified"},
        {"id": "pending", "label": "待分类/待整理", "kind": "pending", "status": "pending"},
    ])
    return {"schema_version": CLASSIFICATION_VERSION, "pages": pages}


def _safe_rel(path: str) -> str:
    posix = PurePosixPath(path)
    if posix.is_absolute() or ".." in posix.parts:
        raise ValueError(f"unsafe relative path: {path}")
    if "\\" in path or re.match(r"^[A-Za-z]:", path):
        raise ValueError(f"unsafe relative path: {path}")
    return str(posix)


def _entry_index(workspace: Path, inventory: Mapping[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for metadata_path, markdown_path in _entry_files(workspace):
        if not markdown_path.exists():
            continue
        metadata = read_json(metadata_path)
        markdown = markdown_path.read_text(encoding="utf-8")
        entries.append({
            "id": metadata.get("id"),
            "title": metadata.get("title"),
            "type": metadata.get("type"),
            "category": metadata.get("category"),
            "problem_family": metadata.get("problem_family", "unknown"),
            "tags": metadata.get("tags", []),
            "summary": metadata.get("summary") or _summary_from_markdown(markdown),
            "search_text": markdown,
            "path": f"entries/{markdown_path.name}",
            "metadata_path": f"entries/{metadata_path.name}",
            "content_sha256": sha256_file(markdown_path),
            "metadata_sha256": sha256_file(metadata_path),
            "source_refs": metadata.get("source_refs", []),
            "evidence_refs": metadata.get("evidence_refs", []),
            "code_refs": metadata.get("code_refs", []),
            "attributes": metadata.get("attributes", {}),
            "relations": metadata.get("relations", {}),
            "status": metadata.get("status", "unread"),
        })
    return sorted(
        entries,
        key=lambda item: (
            str(item.get("category")), str(item.get("title")), str(item.get("id")),
        ),
    )


def _workspace_whitelist(workspace: Path) -> list[Path]:
    paths: list[Path] = []
    for name in (
        "inventory.json", "inventory.md", "sources.json", "sources.md",
        "taxonomy.json", "classification.json", "classification.md", "README.md",
        "plan_startup.md", "literature_collection.md", "literature_harvest_scheme.md",
    ):
        path = workspace / name
        if path.is_file():
            paths.append(path)
    for metadata_path, markdown_path in _entry_files(workspace):
        if metadata_path.is_file():
            paths.append(metadata_path)
        if markdown_path.is_file():
            paths.append(markdown_path)
    categories = workspace / "categories"
    if categories.is_dir():
        paths.extend(path for path in categories.glob("*.md") if path.is_file())
    for folder_name in ("catalogs", "eoh_adapters"):
        folder = workspace / folder_name
        if folder.is_dir():
            paths.extend(
                path for path in folder.rglob("*")
                if path.is_file() and path.suffix in {".json", ".md"}
            )
    return sorted(set(paths))


def _copy_public_files(workspace: Path, stage: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for source in _workspace_whitelist(workspace):
        relative = source.relative_to(workspace).as_posix()
        target = stage / _safe_rel(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        files.append({
            "path": relative,
            "sha256": sha256_file(target),
            "size": target.stat().st_size,
        })
    return files


def _release_input(release: Path) -> Path:
    # Git with core.symlinks=false checks a tracked symlink out as text.
    # Resolve that representation before Path.resolve() loses pointer context.
    if release.name == "current" and release.is_file() and not release.is_symlink():
        target = release.read_text(encoding="utf-8").strip()
        return (release.parent / target).resolve()
    release = release.resolve() if release.exists() else release.absolute()
    if release.is_file() and release.name in {"manifest.json", "index.json", "dashboard.html"}:
        return release.parent
    if release.is_dir() and (release / "releases").is_dir():
        current = release / "current"
        if current.exists() or os.path.lexists(current):
            try:
                return _release_input(current)
            except OSError:
                pass
        pointer = release / "current.path"
        if pointer.exists():
            target = pointer.read_text(encoding="utf-8").strip()
            return (release / target).resolve() if not os.path.isabs(target) else Path(target)
        candidates = sorted(
            (release / "releases").glob("*/manifest.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return candidates[0].parent
        raise FileNotFoundError(f"no current release under {release}")
    if release.name == "current" and not release.exists():
        pointer = release.parent / "current.path"
        if pointer.exists():
            target = pointer.read_text(encoding="utf-8").strip()
            return (release.parent / target).resolve()
    return release


def resolve_release(release: Path) -> Path:
    path = _release_input(release)
    if not path.is_dir() or not (path / "manifest.json").is_file() or not (path / "index.json").is_file():
        raise FileNotFoundError(f"not a knowledge release: {release}")
    return path


def _previous_release(store: Path, current_release_id: str) -> Path | None:
    releases = store / "releases"
    if not releases.exists():
        return None
    # The current pointer is the authoritative publication order.  This also
    # handles manually named releases whose lexical order does not match build
    # order (for example, a sanitized repair release followed by a final one).
    current = store / "current"
    if current.exists() or os.path.lexists(current):
        try:
            pointed = current.resolve()
        except OSError:
            pointed = None
        if (
            pointed is not None
            and pointed.name != current_release_id
            and pointed.is_dir()
            and (pointed / "index.json").is_file()
        ):
            return pointed
    pointer = store / "current.path"
    if pointer.is_file():
        target = pointer.read_text(encoding="utf-8").strip()
        pointed = (store / target).resolve() if target and not os.path.isabs(target) else Path(target)
        if (
            pointed.name != current_release_id
            and pointed.is_dir()
            and (pointed / "index.json").is_file()
        ):
            return pointed
    candidates = [
        path for path in releases.iterdir()
        if path.is_dir()
        and not path.name.startswith(".")
        and path.name != current_release_id
        and (path / "index.json").exists()
    ]
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name)) if candidates else None


def _version_diff(previous: Path | None, entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    old_by_id: dict[str, Mapping[str, Any]] = {}
    previous_id = None
    if previous:
        try:
            old = read_json(previous / "index.json")
            previous_id = old.get("release_id")
            old_by_id = {str(item.get("id")): item for item in old.get("entries", [])}
        except (FileNotFoundError, ValueError):
            previous_id = None
    new_by_id = {str(item.get("id")): item for item in entries}
    added = sorted(set(new_by_id) - set(old_by_id))
    removed = sorted(set(old_by_id) - set(new_by_id))
    changed_body = sorted(
        entry_id
        for entry_id in set(new_by_id) & set(old_by_id)
        if new_by_id[entry_id].get("content_sha256") != old_by_id[entry_id].get("content_sha256")
    )
    changed_meta = sorted(
        entry_id
        for entry_id in set(new_by_id) & set(old_by_id)
        if new_by_id[entry_id].get("metadata_sha256") != old_by_id[entry_id].get("metadata_sha256")
        and entry_id not in changed_body
    )
    changed = sorted(set(changed_body) | set(changed_meta))
    return {
        "previous_release_id": previous_id,
        "added": added,
        "removed": removed,
        "changed": changed,
        "changed_body": changed_body,
        "changed_metadata": changed_meta,
        "added_count": len(added),
        "removed_count": len(removed),
        "changed_count": len(changed),
    }


def _atomic_pointer(store: Path, release_dir: Path) -> str:
    """Point current at a release, with a documented Windows fallback."""
    current = store / "current"
    temp_pointer = store / f".current-{uuid.uuid4().hex}"
    try:
        target = os.path.relpath(release_dir, store)
        os.symlink(target, temp_pointer, target_is_directory=True)
        try:
            os.replace(temp_pointer, current)
        except OSError:
            # Windows often cannot replace an existing directory symlink in
            # one call.  Rename it to a private backup, install the prepared
            # pointer, and restore the backup if the second rename fails.
            if not (current.exists() or os.path.lexists(current)):
                raise
            backup = store / f".current-old-{uuid.uuid4().hex}"
            os.replace(current, backup)
            installed = False
            try:
                os.replace(temp_pointer, current)
                installed = True
            except Exception:
                if not (current.exists() or os.path.lexists(current)):
                    os.replace(backup, current)
                raise
            finally:
                if installed and (backup.exists() or os.path.lexists(backup)):
                    backup.unlink()
        fallback = store / "current.path"
        if fallback.exists():
            fallback.unlink()
        return "symlink"
    except (OSError, NotImplementedError):
        try:
            if temp_pointer.exists() or os.path.lexists(temp_pointer):
                temp_pointer.unlink()
        except OSError:
            pass
        pointer = store / "current.path"
        temp_file = store / f".current-path-{uuid.uuid4().hex}"
        if current.exists() or os.path.lexists(current):
            raise OSError(
                "cannot create knowledge_store/current symlink on this platform; "
                "existing current was left untouched; use the explicit release path"
            )
        temp_file.write_text(f"releases/{release_dir.name}\n", encoding="utf-8")
        os.replace(temp_file, pointer)
        return "path_file"


def build_release(
    workspace: Path,
    store: Path,
    release_id: str | None = None,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    store = store.resolve()
    validation = validate_workspace(workspace)
    if not validation["ok"]:
        message = "; ".join(validation["errors"][:8])
        raise ValueError("workspace validation failed: " + message)
    inventory = read_json(workspace / "inventory.json")
    source_doc = read_json(workspace / "sources.json")
    taxonomy_path = workspace / "taxonomy.json"
    entries = _entry_index(workspace, inventory)
    taxonomy = read_json(taxonomy_path) if taxonomy_path.exists() else _default_taxonomy(inventory, entries)
    protocol_files = []
    for path in _workspace_whitelist(workspace):
        relative = path.relative_to(workspace).as_posix()
        if relative.startswith("catalogs/") or relative.startswith("eoh_adapters/") or relative in {
            "literature_harvest_scheme.md", "plan_startup.md", "literature_collection.md",
        }:
            protocol_files.append({"path": relative, "sha256": sha256_file(path)})
    protocol_files.sort(key=lambda item: item["path"])
    published_inputs = []
    for name in ("inventory.json", "classification.json", "README.md"):
        extra = workspace / name
        if extra.is_file():
            published_inputs.append({"path": name, "sha256": sha256_file(extra)})
    dashboard_path = Path(__file__).with_name("dashboard.py")
    tools_fingerprint = {
        "knowledge_tools": __version__,
        "dashboard_sha256": sha256_file(dashboard_path) if dashboard_path.is_file() else None,
    }
    content_seed = canonical_json({
        "inventory": inventory.get("source_main_sha"),
        "entries": entries,
        "sources": source_doc,
        "taxonomy": taxonomy,
        "protocol_files": protocol_files,
        "published_inputs": published_inputs,
        "tools": tools_fingerprint,
    })
    content_digest = sha256_bytes(content_seed)
    if not release_id:
        timestamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        release_id = timestamp + "-" + content_digest[:12]
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", release_id):
        raise ValueError("release_id must contain only letters, digits, '.', '_' or '-'")

    store.mkdir(parents=True, exist_ok=True)
    releases = store / "releases"
    releases.mkdir(parents=True, exist_ok=True)
    for existing in releases.iterdir():
        if not existing.is_dir() or existing.name.startswith("."):
            continue
        manifest_path = existing / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            published = read_json(manifest_path)
        except (OSError, ValueError, UnicodeError):
            continue
        if published.get("content_digest") == content_digest and existing.name != release_id:
            raise ValueError(
                f"identical content already published as {existing.name}; reuse that release instead of a new id"
            )
    final = releases / release_id
    if final.exists():
        raise FileExistsError(f"release already exists and is immutable: {final}")
    stage = releases / f".staging-{release_id}-{uuid.uuid4().hex}"
    stage.mkdir(parents=True)
    try:
        _copy_public_files(workspace, stage)
        index = {
            "schema_version": SCHEMA_VERSION,
            "release_id": release_id,
            "generated_at": utc_now(),
            "source_main_sha": inventory.get("source_main_sha"),
            "entries": entries,
            "categories": taxonomy.get("pages", []),
            "search_fields": ["id", "title", "summary", "category", "problem_family", "tags"],
        }
        write_json(stage / "index.json", index)
        write_json(stage / "taxonomy.json", taxonomy)
        write_json(stage / "sources.json", source_doc)
        relation_rows = []
        for entry in entries:
            relation_rows.append({
                "entry_id": entry.get("id"),
                "relations": entry.get("relations", {}),
                "source_refs": entry.get("source_refs", []),
                "evidence_refs": entry.get("evidence_refs", []),
            })
        write_json(stage / "relations.json", {
            "schema_version": SCHEMA_VERSION,
            "release_id": release_id,
            "rows": relation_rows,
        })
        previous = _previous_release(store, release_id)
        diff = _version_diff(previous, entries)
        write_json(stage / "version_diff.json", diff)
        pending = [
            item for item in entries
            if item.get("status") in {"pending", "unread"} or item.get("category") == "pending"
        ]
        bodies: dict[str, str] = {}
        for item in entries:
            rel = item.get("path")
            if not rel:
                continue
            body_path = workspace / str(rel)
            if body_path.is_file():
                bodies[str(item.get("id"))] = body_path.read_text(encoding="utf-8")
        (stage / "dashboard.html").write_text(
            dashboard_html(
                release_id, index, taxonomy, source_doc, pending, diff, inventory,
                bodies=bodies,
            ),
            encoding="utf-8",
            newline="\n",
        )
        # The manifest hashes every other publication file.  Its own detached
        # hash is written to manifest.sha256 to avoid a self-referential hash.
        manifest_files = []
        for path in sorted(
            item for item in stage.rglob("*")
            if item.is_file() and item.name not in {"manifest.json", "manifest.sha256"}
        ):
            manifest_files.append({
                "path": path.relative_to(stage).as_posix(),
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            })
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "release_id": release_id,
            "created_at": utc_now(),
            "source_main_sha": inventory.get("source_main_sha"),
            "classification_rule_version": CLASSIFICATION_VERSION,
            "build_tool_version": __version__,
            "content_digest": content_digest,
            "files": manifest_files,
            "self_hash_file": "manifest.sha256",
            "self_hash_excluded_from_files": True,
            "publication_policy": {
                "whitelist_only": True,
                "full_text_downloads": "excluded unless explicitly permitted",
                "model_or_solver_calls": False,
            },
        }
        write_json(stage / "manifest.json", manifest)
        (stage / "manifest.sha256").write_text(
            sha256_file(stage / "manifest.json") + "  manifest.json\n",
            encoding="utf-8",
            newline="\n",
        )
        for item in manifest_files:
            target = stage / item["path"]
            if not target.exists() or sha256_file(target) != item["sha256"]:
                raise ValueError(f"staged file hash mismatch: {item['path']}")
        stage.rename(final)
        pointer_mode = _atomic_pointer(store, final)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return {
        "release_id": release_id,
        "release": str(final),
        "store": str(store),
        "pointer": pointer_mode,
        "manifest_sha256": sha256_file(final / "manifest.json"),
        "entry_count": len(entries),
        "source_count": len(source_doc.get("sources", [])),
    }


def validate_release(release: Path) -> dict[str, Any]:
    path = resolve_release(release)
    errors: list[str] = []
    try:
        manifest = read_json(path / "manifest.json")
    except (FileNotFoundError, ValueError, UnicodeError) as exc:
        return {
            "release": str(path),
            "release_id": None,
            "ok": False,
            "errors": [f"invalid manifest.json: {exc}"],
            "manifest_sha256": None,
        }
    if not isinstance(manifest, Mapping):
        return {
            "release": str(path),
            "release_id": None,
            "ok": False,
            "errors": ["manifest.json must contain an object"],
            "manifest_sha256": sha256_file(path / "manifest.json"),
        }
    listed_paths: set[str] = set()
    manifest_files = manifest.get("files", [])
    if not isinstance(manifest_files, list):
        errors.append("manifest files must be a list")
        manifest_files = []
    for item in manifest_files:
        if not isinstance(item, Mapping):
            errors.append("manifest file entry is not an object")
            continue
        relative = item.get("path")
        if not isinstance(relative, str):
            errors.append("manifest file entry has no path")
            continue
        try:
            safe_relative = _safe_rel(relative)
        except (TypeError, ValueError) as exc:
            errors.append(f"unsafe release file path {relative!r}: {exc}")
            continue
        if safe_relative in listed_paths:
            errors.append(f"duplicate manifest file: {safe_relative}")
        listed_paths.add(safe_relative)
        target = path / safe_relative
        digest = item.get("sha256")
        if not isinstance(digest, str) or not HEX64.match(digest):
            errors.append(f"invalid release hash: {relative}")
        elif not target.is_file():
            errors.append(f"missing release file: {relative}")
        elif sha256_file(target) != digest:
            errors.append(f"release hash mismatch: {relative}")
    actual_paths = {
        candidate.relative_to(path).as_posix()
        for candidate in path.rglob("*")
        if candidate.is_file() and candidate.name not in {"manifest.json", "manifest.sha256"}
    }
    for extra in sorted(actual_paths - listed_paths):
        errors.append(f"unlisted release file: {extra}")
    if manifest.get("release_id") and path.name != manifest.get("release_id"):
        errors.append("manifest release_id does not match release directory")
    try:
        index = read_json(path / "index.json")
        if not isinstance(index, Mapping):
            errors.append("index.json must contain an object")
            index = {}
        if index.get("release_id") != manifest.get("release_id"):
            errors.append("index release_id does not match manifest")
        for entry in index.get("entries", []):
            relative = entry.get("path")
            if not isinstance(relative, str):
                errors.append(f"index entry {entry.get('id')} has no path")
                continue
            try:
                target = path / _safe_rel(relative)
            except (TypeError, ValueError) as exc:
                errors.append(f"unsafe index path for {entry.get('id')}: {exc}")
                continue
            if not target.is_file():
                errors.append(f"index entry body missing: {relative}")
            elif entry.get("content_sha256") != sha256_file(target):
                errors.append(f"index content hash mismatch: {entry.get('id')}")
    except (FileNotFoundError, ValueError, TypeError) as exc:
        errors.append(f"invalid release index: {exc}")
    self_hash_name = manifest.get("self_hash_file", "manifest.sha256")
    try:
        detached = path / _safe_rel(str(self_hash_name))
    except (TypeError, ValueError) as exc:
        detached = None
        errors.append(f"unsafe manifest self hash path: {exc}")
    if detached is not None and detached.exists():
        fields = detached.read_text(encoding="utf-8").split()
        expected = fields[0] if fields else ""
        actual = sha256_file(path / "manifest.json")
        if expected != actual:
            errors.append("manifest.sha256 does not match manifest.json")
    elif detached is not None:
        errors.append("missing manifest.sha256")
    return {
        "release": str(path),
        "release_id": manifest.get("release_id"),
        "ok": not errors,
        "errors": errors,
        "manifest_sha256": sha256_file(path / "manifest.json"),
    }


def _load_release_index(release: Path) -> tuple[Path, dict[str, Any]]:
    path = resolve_release(release)
    return path, read_json(path / "index.json")


_SEARCH_FIELD_WEIGHTS = {
    "title": 3.0, "tags": 3.0, "summary": 2.0, "id": 2.0,
    "attributes": 2.0, "category": 1.0, "problem_family": 1.0,
    "relations": 1.0, "search_text": 1.0,
}
_TYPE_WEIGHT = {
    "method": 3.0, "implementation": 2.4, "evidence": 2.0,
    "framework": 1.2, "literature": 1.1, "problem": 1.0, "pending": 0.4,
}
# Query-side bilingual stems. Family aliases also live on FAMILY_INFO / taxonomy pages.
_TERM_ALIASES = {
    "构造": ["construct", "construction"],
    "装箱": ["binpacking", "onlinebinpacking", "obp"],
    "旅行商": ["tsp", "travelingsalesman"],
    "背包": ["knapsack"],
    "车辆路径": ["cvrp", "vehiclerouting"],
}


def _norm_alias(text: str) -> str:
    return re.sub(r"[-_\s]", "", str(text).casefold())


def _search_alias_map(release_path: Path) -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for family, info in FAMILY_INFO.items():
        alias_map[_norm_alias(family)] = family
        for alias in info.get("aliases") or []:
            key = _norm_alias(alias)
            if key:
                alias_map[key] = family
    taxonomy_path = release_path / "taxonomy.json"
    if taxonomy_path.is_file():
        try:
            taxonomy = read_json(taxonomy_path)
        except (OSError, ValueError):
            taxonomy = {}
        for page in taxonomy.get("pages") or []:
            if not isinstance(page, Mapping) or not page.get("id"):
                continue
            family = str(page["id"])
            for alias in [page.get("label"), *(page.get("aliases") or [])]:
                key = _norm_alias(alias or "")
                if key:
                    alias_map[key] = family
    return alias_map


def _flatten_mapping(value: Any) -> str:
    """Flatten a nested mapping/list into one space-joined string."""
    if value is None:
        return ""
    parts: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                parts.append(str(key))
                walk(child)
        elif isinstance(node, (list, tuple)):
            for child in node:
                walk(child)
        else:
            parts.append(str(node))

    walk(value)
    return " ".join(parts)


def search_release(release: Path, query: str, limit: int = 10) -> dict[str, Any]:
    path, index = _load_release_index(release)
    raw_terms = re.findall(r"\w+(?:[-_]\w+)*", query.casefold())
    terms: list[str] = []
    for raw in raw_terms:
        term = re.sub(r"[-_]", "", raw)
        if len(term) == 1 and term.isascii():
            continue
        if term not in terms:
            terms.append(term)
    alias_map = _search_alias_map(path)
    expanded: list[str] = []
    for i, term in enumerate(terms):
        expanded.append(term)
        for extra in _TERM_ALIASES.get(term, []):
            expanded.append(_norm_alias(extra))
        if term in alias_map:
            family = alias_map[term]
            expanded.append(_norm_alias(family))
            for alias in FAMILY_INFO.get(family, {}).get("aliases") or []:
                expanded.append(_norm_alias(alias))
        if i + 1 < len(terms):
            joined = terms[i] + terms[i + 1]
            if joined in alias_map:
                family = alias_map[joined]
                expanded.append(_norm_alias(family))
                for alias in FAMILY_INFO.get(family, {}).get("aliases") or []:
                    expanded.append(_norm_alias(alias))
    terms = []
    for term in expanded:
        if term not in terms:
            terms.append(term)
    if not terms:
        raise ValueError("query must contain at least one non-space term")
    limit = max(0, int(limit))
    results = []
    for entry in index.get("entries", []):
        field_texts: dict[str, str] = {}
        for key in _SEARCH_FIELD_WEIGHTS:
            value = entry.get(key)
            if key == "tags":
                if isinstance(value, list):
                    value = " ".join(str(item) for item in value)
                else:
                    value = str(value or "")
            elif key in {"attributes", "relations"}:
                value = _flatten_mapping(value)
            else:
                value = str(value or "")
            field_texts[key] = re.sub(r"[-_]", "", value.casefold())
        field_hits = 0.0
        matched_terms: set[str] = set()
        for key, weight in _SEARCH_FIELD_WEIGHTS.items():
            hits = sum(1 for term in terms if term in field_texts[key])
            if hits:
                field_hits += weight * hits
                for term in terms:
                    if term in field_texts[key]:
                        matched_terms.add(term)
        if not matched_terms:
            continue
        coverage = len(matched_terms) / len(terms)
        score = round(
            coverage
            * (1 + field_hits / (len(terms) * sum(_SEARCH_FIELD_WEIGHTS.values())))
            * _TYPE_WEIGHT.get(str(entry.get("type") or ""), 1.0),
            4,
        )
        results.append({
            "id": entry.get("id"),
            "title": entry.get("title"),
            "summary": entry.get("summary", ""),
            "category": entry.get("category"),
            "problem_family": entry.get("problem_family", "unknown"),
            "type": entry.get("type"),
            "version": index.get("release_id"),
            "release": str(path),
            "content_sha256": entry.get("content_sha256"),
            "score": score,
        })
    results.sort(key=lambda item: (-item["score"], item["title"] or item["id"] or ""))
    return {
        "query": query,
        "release_id": index.get("release_id"),
        "release": str(path),
        "total": len(results),
        "count": min(len(results), limit),
        "results": results[:limit],
    }


def read_entry(release: Path, entry_id: str) -> dict[str, Any]:
    path, index = _load_release_index(release)
    matches = [item for item in index.get("entries", []) if item.get("id") == entry_id]
    if not matches:
        raise KeyError(f"entry not found: {entry_id}")
    item = matches[0]
    relative = item.get("path")
    if not isinstance(relative, str):
        raise ValueError(f"entry {entry_id} has no path")
    body_path = path / _safe_rel(relative)
    body = body_path.read_text(encoding="utf-8")
    body_hash = sha256_file(body_path)
    expected_hash = item.get("content_sha256")
    if expected_hash and expected_hash != body_hash:
        raise ValueError(f"content hash mismatch for entry {entry_id}")
    result = {
        "id": entry_id,
        "release_id": index.get("release_id"),
        "release": str(path),
        "title": item.get("title"),
        "type": item.get("type"),
        "category": item.get("category"),
        "problem_family": item.get("problem_family", "unknown"),
        "content_sha256": body_hash,
        "source_refs": item.get("source_refs", []),
        "evidence_refs": item.get("evidence_refs", []),
        "body": body,
    }
    sources_path = path / "sources.json"
    if sources_path.exists():
        source_doc = read_json(sources_path)
        by_id = {
            source.get("id"): source
            for source in source_doc.get("sources", [])
            if isinstance(source, Mapping)
        }
        result["sources"] = [
            by_id[source_id]
            for source_id in result["source_refs"]
            if source_id in by_id
        ]
    else:
        result["sources"] = []
    return result
