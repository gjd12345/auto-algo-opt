"""Offline, dev-only consolidation of evidence-linked L1/L2 cards."""

from __future__ import annotations

import ast
import hashlib
import json
import math
import re
import stat
from collections import defaultdict
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from agent_skill_loop.file_lock import exclusive_file_lock

from .api import (
    MemoryAPI,
    MemoryEntry,
    _atomic_text,
    _validate_anchor,
    _validate_entry,
    _validate_scope,
    memory_is_active,
    solution_execution_ast_sha256,
)
from .problem_vocab import problem_family


_SCOPE_IDENTITY = ("problem", "interface_id", "fleet_policy", "evaluator_version")
_DEV_SPLITS = ("dev", "dev_train")
_FORBIDDEN_LABEL = re.compile(r"blind|custody|(?:^|[^a-z])select(?:ion)?(?:$|[^a-z])", re.I)
_FORBIDDEN_PATH = re.compile(r"(?:^|[^a-z])blind(?:$|[^a-z])|^(?:cvrp_|tsp_|obp_|bpp_|m\d+_|locked_)?(?:m\d+_)?select(?:ion)?(?:$|[_.-])", re.I)
_FORBIDDEN_VALUE = re.compile(
    r"\bsealed_seed_token\b|\b(?:customer_coordinates|coordinates|demands)\b\s*[\"']?\s*[:=]\s*[\[{]", re.I,
)
_SHA256 = re.compile(r"[a-f0-9]{64}")
_CLAIM_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
_REFERENCE = re.compile(r"[\w-]+/(?:insight|antipattern|solution)_[A-Za-z0-9_-]+@v\d{4}", re.ASCII)
_GEOMETRY_FIELDS = ("spatial_regime", "demand_cv_regime", "eccentricity_regime")
_C2_BUDGET_MS = 500.0
_C2_RATIO_LIMIT = 8.0
_C2_RECEIPT_SCHEMA = "m6-c2-admission-receipts/v1"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def evidence_digest(facts: Mapping[str, Any]) -> str:
    """Digest for inline facts, using canonical UTF-8 JSON bytes."""
    return _sha256(_json(facts).encode("utf-8"))


def _forbidden_path(path: Path) -> bool:
    return any(_FORBIDDEN_PATH.search(part) or part.casefold().startswith(".agent_skill_custody")
               for part in path.parts)


def _check_dev(value: Any) -> None:
    """Screen recursively before any source is handed to the consolidator."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("auto_dream_evidence_key_invalid")
            label = re.sub(r"[^a-z0-9]", "", key.casefold())
            if label in {"sealedseedtoken", "customercoordinates", "rawcustomercoordinates", "coordinates",
                         "rawcoordinates", "demands", "rawdemands"}:
                raise ValueError("auto_dream_confidential_evidence")
            if "blind" in label or label.startswith("custody"):
                raise ValueError("auto_dream_non_dev_evidence")
            if isinstance(item, str):
                if ("suite" in label or "split" in label or "role" in label
                        or label in {"profile", "exposurestatus", "schemaversion", "sourcerunid"}):
                    if item.casefold() != "dev_selection" and _FORBIDDEN_LABEL.search(item):
                        raise ValueError("auto_dream_non_dev_evidence")
                if (label.endswith("ref") or label == "sourcesessionroot") and _forbidden_path(
                    Path(item.removeprefix("evaluation:"))
                ):
                    raise ValueError("auto_dream_non_dev_evidence")
            if label == "evidencerefs" and isinstance(item, list) and any(
                isinstance(ref, str) and _forbidden_path(Path(ref.removeprefix("evaluation:"))) for ref in item
            ):
                raise ValueError("auto_dream_non_dev_evidence")
            _check_dev(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _check_dev(item)
    elif isinstance(value, str) and _FORBIDDEN_VALUE.search(value):
        raise ValueError("auto_dream_confidential_evidence")


@dataclass(frozen=True)
class ClaimEvidence:
    claim_id: str
    applicability_scope: dict[str, Any]
    denominators: dict[str, int]
    adverse_results: list[str | dict[str, Any]]
    contradictions: list[str | dict[str, Any]]
    code_anchor: dict[str, str]
    evaluation_facts_sha256: str
    evidence_ref: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ClaimEvidence:
        _check_dev(value)
        required = {field.name for field in fields(cls)}
        if not isinstance(value, Mapping) or not required.issubset(value):
            raise ValueError("auto_dream_claim_evidence_fields_required")
        data = {key: value[key] for key in required}
        if not isinstance(data["claim_id"], str) or not _CLAIM_ID.fullmatch(data["claim_id"]):
            raise ValueError("auto_dream_claim_id_invalid")
        scope = data["applicability_scope"]
        if not isinstance(scope, dict) or not set(_SCOPE_IDENTITY).issubset(scope):
            raise ValueError("auto_dream_claim_scope_incomplete")
        _validate_scope(scope, project=scope["problem"], required=False)
        counts = data["denominators"]
        if (not isinstance(counts, dict) or not counts
                or any(not key or type(count) is not int or count < 0 for key, count in counts.items())
                or not any(counts.values())):
            raise ValueError("auto_dream_claim_denominators_invalid")
        for key in ("adverse_results", "contradictions"):
            if not isinstance(data[key], list) or any(
                not ((isinstance(item, str) and item.strip()) or (isinstance(item, dict) and item))
                for item in data[key]
            ):
                raise ValueError(f"auto_dream_claim_{key}_invalid")
        _validate_anchor(data["code_anchor"])
        digest, evidence_ref = data["evaluation_facts_sha256"], data["evidence_ref"]
        if (not isinstance(digest, str) or not _SHA256.fullmatch(digest)
                or not isinstance(evidence_ref, str) or not evidence_ref.strip() or len(evidence_ref) > 1024):
            raise ValueError("auto_dream_claim_provenance_invalid")
        return cls(**json.loads(_json(data)))


@dataclass(frozen=True)
class ClaimEvidenceManifest:
    claims: tuple[ClaimEvidence, ...]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ClaimEvidenceManifest:
        _check_dev(value)
        if not isinstance(value, Mapping) or not isinstance(value.get("claims"), list) or not value["claims"]:
            raise ValueError("auto_dream_claims_required")
        claims = tuple(sorted((ClaimEvidence.from_dict(item) for item in value["claims"]), key=lambda item: item.claim_id))
        if len({item.claim_id for item in claims}) != len(claims):
            raise ValueError("auto_dream_duplicate_claim_id")
        return cls(claims)

    def as_dict(self) -> dict[str, Any]:
        return {"claims": [asdict(claim) for claim in self.claims]}

    def validate_preserves(self, source: ClaimEvidenceManifest) -> None:
        """Require exact claim-level preservation, including empty caveat lists."""
        if self != source:
            raise ValueError("auto_dream_claim_evidence_changed")


def _is_link(path: Path) -> bool:
    return path.is_symlink() or (path.exists() and bool(
        getattr(path.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ))


def _read_path(path: Path) -> Path:
    resolved = path.resolve(strict=True)
    if (_forbidden_path(path) or _forbidden_path(resolved)
            or any(_is_link(part) for part in (path, *path.parents))):
        raise ValueError("auto_dream_non_dev_path")
    return resolved


def _write_root(path: Path) -> Path:
    resolved = path.resolve()
    for item in (path.absolute(), resolved):
        parts = tuple(part.casefold() for part in item.parts)
        if (set(parts) & {"eoh_frozen", "eohs_v1", ".env", ".secrets"}
                or any(part.startswith(".agent_skill_custody") for part in parts)
                or any(a == "knowledge_store" and b in {"current", "releases"} for a, b in zip(parts, parts[1:]))
                or any(_is_link(part) for part in (item, *item.parents))):
            raise ValueError("auto_dream_output_path_forbidden")
    return resolved


def _load_artifact(path: Path) -> tuple[Mapping[str, Any], Mapping[str, Any], str, str]:
    path = _read_path(path)
    raw = path.read_bytes()
    document = json.loads(raw)
    _check_dev(document)
    if not isinstance(document, dict) or document.get("split") not in _DEV_SPLITS:
        raise ValueError("auto_dream_dev_artifact_required")
    inline, ref = document.get("evaluation_facts"), document.get("evaluation_facts_ref")
    if (inline is None) == (ref is None):
        raise ValueError("auto_dream_evaluation_facts_required")
    if ref is not None:
        if not isinstance(ref, str):
            raise ValueError("auto_dream_evaluation_facts_path_invalid")
        rel = Path(ref)
        if rel.is_absolute() or rel.anchor or ".." in rel.parts:
            raise ValueError("auto_dream_evaluation_facts_path_invalid")
        facts_path = _read_path(path.parent / rel)
        facts_raw = facts_path.read_bytes()
        facts, digest = json.loads(facts_raw), _sha256(facts_raw)
    else:
        facts, digest = inline, evidence_digest(inline)
    _check_dev(facts)
    if not isinstance(facts, dict) or ("split" in facts and facts["split"] not in _DEV_SPLITS):
        raise ValueError("auto_dream_dev_facts_required")
    return document, facts, digest, _sha256(raw)


def _candidate_ast(candidate: Mapping[str, Any]) -> str | None:
    recorded = candidate.get("canonical_ast_sha256")
    if isinstance(recorded, str) and _SHA256.fullmatch(recorded):
        return recorded
    code = candidate.get("code")
    if not isinstance(code, str) or _sha256(code.encode("utf-8")) != candidate.get("code_sha256"):
        return None
    try:
        canonical = ast.unparse(ast.parse(code))
    except (SyntaxError, ValueError, RecursionError):
        return None
    return _sha256(canonical.encode("utf-8"))


def _match_evidence(claim: ClaimEvidence, facts: Mapping[str, Any], digest: str) -> Mapping[str, Any]:
    scope = claim.applicability_scope
    refs, candidates = facts.get("evidence_refs"), facts.get("candidates")
    selection = facts.get("interface_selection") or {}
    if not isinstance(selection, dict):
        raise ValueError("auto_dream_evaluation_provenance_mismatch")
    top_interface = facts.get("interface_id", selection.get("template_id"))
    if (claim.evaluation_facts_sha256 != digest or scope["problem"] != facts.get("problem")
            or scope["evaluator_version"] != facts.get("evaluator_version", facts.get("evaluator_hash"))
            or (top_interface is not None and scope["interface_id"] != top_interface)
            or scope["fleet_policy"] != facts.get("fleet_policy", scope["fleet_policy"])
            or not isinstance(refs, list) or claim.evidence_ref not in refs or not isinstance(candidates, list)):
        raise ValueError("auto_dream_evaluation_provenance_mismatch")
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if claim.evidence_ref.startswith("evaluation:") and claim.evidence_ref != f"evaluation:{candidate.get('evaluation_id')}":
            continue
        cand_interface = candidate.get("interface_id", top_interface)
        if cand_interface != scope["interface_id"]:
            continue
        if "code_sha256" in claim.code_anchor and candidate.get("code_sha256") != claim.code_anchor["code_sha256"]:
            continue
        if "canonical_ast_sha256" in claim.code_anchor and _candidate_ast(candidate) != claim.code_anchor["canonical_ast_sha256"]:
            continue
        return candidate
    raise ValueError("auto_dream_evaluation_provenance_mismatch")


def _source_card(stores: Sequence[MemoryAPI], reference: str) -> dict[str, Any]:
    if not isinstance(reference, str) or not _REFERENCE.fullmatch(reference):
        raise ValueError("auto_dream_source_reference_invalid")
    records = []
    stem, version = reference.rsplit("@v", 1)
    for api in stores:
        suffix = ".json" if api.json_only else ".md"
        path = api.store / f"{stem}__v{version}{suffix}"
        if not api.json_only and version == "0001" and not path.is_file():
            path = api.store / f"{stem}.md"
        if path.is_symlink() or path.with_suffix(".json").is_symlink():
            raise ValueError("auto_dream_source_card_link")
        if not path.is_file():
            continue
        _read_path(path)
        sidecar = path.with_suffix(".json")
        if sidecar.is_file():
            _read_path(sidecar)
        card = api.read_version(reference)
        _check_dev(card)
        entry = MemoryEntry(**{field.name: card.get(field.name) for field in fields(MemoryEntry)})
        if card["truncated"] or api.card_head(entry) != reference or not memory_is_active(card):
            raise ValueError("auto_dream_inactive_source_card")
        records.append({**entry.as_dict(), "provenance": card["provenance"]})
    if not records or any(record != records[0] for record in records[1:]):
        raise ValueError("auto_dream_source_reference_missing_or_ambiguous")
    return records[0]


def _entry(raw: Mapping[str, Any], claim: ClaimEvidence, candidate: Mapping[str, Any],
           stores: Sequence[MemoryAPI]) -> tuple[MemoryEntry, Mapping[str, Any]]:
    reference, inline = raw.get("source_reference"), raw.get("entry")
    if (reference is None) == (inline is None):
        raise ValueError("auto_dream_source_card_required")
    source = _source_card(stores, reference) if reference is not None else inline
    if not isinstance(source, dict) or any(not isinstance(source.get(key), str) for key in (
        "name", "description", "type", "project", "scene", "body",
    )) or not isinstance(source.get("provenance", {}), Mapping):
        raise ValueError("auto_dream_source_card_required")
    card = MemoryEntry(**{field.name: source.get(field.name) for field in fields(MemoryEntry)})
    _validate_entry(card, publication=False)
    if card.code_anchor is not None:
        _validate_anchor(card.code_anchor)
    if source.get("enabled") is False:
        raise ValueError("auto_dream_inactive_source_card")
    scope = claim.applicability_scope
    provenance = source.get("provenance", {})
    # Session cards index by problem entrypoint while their applicability is
    # frozen against the selected template. Exact typed scope is authoritative.
    from agent_skill_loop.problems.base import get_problem
    supported_scenes = {scope["interface_id"]}
    try:
        supported_scenes.add(get_problem(scope["problem"]).entrypoint)
    except ValueError:
        pass
    if (card.project != scope["problem"] or (card.scene not in supported_scenes and card.applicability_scope != scope)
            or card.applicability_scope not in (None, scope)
            or any(claim.code_anchor.get(key) != digest for key, digest in (card.code_anchor or {}).items())
            or provenance.get("evaluation_facts_sha256", claim.evaluation_facts_sha256) != claim.evaluation_facts_sha256
            or provenance.get("evidence_ref", claim.evidence_ref) != claim.evidence_ref):
        raise ValueError("auto_dream_source_evidence_mismatch")
    if card.type == "solution":
        try:
            canonical_ast_sha256 = solution_execution_ast_sha256(card.body)
        except ValueError as exc:
            raise ValueError("auto_dream_unverified_solution") from exc
        if (reference is None or candidate.get("valid") is not True or not provenance.get("parent_version_id")
                or provenance.get("candidate_code_sha256") != claim.code_anchor.get("code_sha256")
                or canonical_ast_sha256 != claim.code_anchor.get("canonical_ast_sha256")
                or canonical_ast_sha256 != provenance.get("canonical_ast_sha256")
                or provenance.get("evaluator_hash") != scope["evaluator_version"]
                or provenance.get("interface_id") not in supported_scenes):
            raise ValueError("auto_dream_unverified_solution")
    if problem_family(card.project) == "online_obp":
        from .retrieval_m35 import admission_allowed
        metrics = candidate.get("metrics") or {}
        if not isinstance(metrics, Mapping):
            raise ValueError("auto_dream_obp_prefix_evidence_required")
        probe = candidate.get("prefix_trace_equal", metrics.get("prefix_trace_equal"))
        scope_context = {**scope, "n": tuple(scope.get("n_range", ())),
                         "budget_ms": scope.get("budget_ms_range", (None,))[0]}
        evidence = {**source, "evidence": candidate, "diagnostics": metrics, "prefix_trace_equal": probe}
        if probe is not True or not admission_allowed(evidence, scope_context):
            raise ValueError("auto_dream_obp_prefix_evidence_required")
        provenance = {**provenance, "prefix_trace_equal": "true"}
    entry = replace(card, applicability_scope=scope, code_anchor=claim.code_anchor,
                    validity_status=card.validity_status or "active", evidence_tier=card.evidence_tier or "single_run")
    if not memory_is_active(entry.as_dict()):
        raise ValueError("auto_dream_inactive_source_card")
    _validate_entry(entry)
    return entry, provenance


def _geometry_scale_tags(*sources: Mapping[str, Any]) -> dict[str, Any]:
    tags: dict[str, Any] = {}
    for source in sources:
        geometry = source.get("geometry_scale")
        fields = {**source, **geometry} if isinstance(geometry, Mapping) else source
        for key in _GEOMETRY_FIELDS:
            values = fields.get(key)
            if isinstance(values, str):
                values = [values]
            if isinstance(values, (list, tuple)):
                normalized = {re.sub(r"[\s-]+", "_", value.strip().casefold()) for value in values
                              if isinstance(value, str)}
                regimes = sorted(value for value in normalized if re.fullmatch(r"[a-z0-9_]{1,48}", value))
                if 0 < len(regimes) <= 16:
                    tags[key] = regimes
        bounds = fields.get("scale_range")
        if (isinstance(bounds, (list, tuple)) and len(bounds) == 2
                and all(type(value) is int and value > 0 for value in bounds) and bounds[0] <= bounds[1]):
            tags["scale_range"] = list(bounds)
    return tags


def screen_cvrp_c2_solution(
    code: str,
    *,
    template_id: str = "cvrp_parallel_merge_static",
    template_version: str = "v2",
    postprocess_mode: str = "relocate_2opt",
) -> tuple[dict[str, Any], str | None]:
    """Run the deterministic C2 joint multiscale probe screen for an evolved CVRP hook."""
    from agent_skill_loop.interface_design.multiscale import ONLINE_C2_JOINT_PROBES
    from agent_skill_loop.interface_design.templates import build_classic_cw_static_design
    from agent_skill_loop.interface_design.validator import InterfaceValidator

    telemetry = {"c2_multiscale_screen_passed": False, "c2_latency_ratio_max": None,
                 "c2_probe_budget_ms": _C2_BUDGET_MS}
    if template_id != "cvrp_parallel_merge_static":
        return telemetry, "c2_unsupported_solution_interface"
    if template_version != "v2":
        return telemetry, "c2_solution_template_version_mismatch"
    if postprocess_mode not in ("none", "relocate_2opt"):
        return telemetry, "c2_solution_postprocess_mode_mismatch"
    try:
        design = build_classic_cw_static_design(template_version="v2", postprocess_mode=postprocess_mode)
        validator = InterfaceValidator(instance_time_budget_ms=_C2_BUDGET_MS, outer_timeout_s=8.0)
        screen = validator.validate_evolved_hook_c2_joint_screen(
            design, hook_code_override=code, max_n200_n100_ratio=_C2_RATIO_LIMIT,
        )
    except (KeyError, OSError, RecursionError, SyntaxError, TypeError, ValueError) as exc:
        return telemetry, f"c2_probe_error:{type(exc).__name__}"
    ratios = [value for pair in screen.get("pairs", []) if isinstance(pair, Mapping)
              and type(value := pair.get("ratio_200_100")) in (int, float) and math.isfinite(value) and value >= 0]
    telemetry["c2_latency_ratio_max"] = max(ratios, default=None)
    if screen.get("passed") is not True:
        error_code = screen.get("error_code")
        reason = error_code if isinstance(error_code, str) and re.fullmatch(r"[a-z0-9_]{1,128}", error_code) else None
        return telemetry, reason or "c2_joint_screen_failed"
    if len(ratios) != len(ONLINE_C2_JOINT_PROBES) // 2 or max(ratios) > _C2_RATIO_LIMIT:
        return telemetry, "c2_joint_probe_protocol"
    telemetry.update(_geometry_scale_from_probes(ONLINE_C2_JOINT_PROBES), c2_multiscale_screen_passed=True)
    return telemetry, None


def _screen_c2_solution(claim: ClaimEvidence, candidate: Mapping[str, Any], facts: Mapping[str, Any],
                        ) -> tuple[dict[str, Any], str | None]:
    telemetry = {"c2_multiscale_screen_passed": False, "c2_latency_ratio_max": None,
                 "c2_probe_budget_ms": _C2_BUDGET_MS}
    if any(source.get("synthetic") is True or source.get("source_kind") in ("synthetic", "mock")
           for source in (candidate, facts)):
        return telemetry, "c2_synthetic_solution_evidence"
    scope = claim.applicability_scope
    if problem_family(scope["problem"]) != "cvrp" or scope["interface_id"] != "cvrp_parallel_merge_static":
        return telemetry, "c2_unsupported_solution_interface"
    code = candidate.get("code")
    if not isinstance(code, str) or _sha256(code.encode("utf-8")) != claim.code_anchor.get("code_sha256"):
        return telemetry, "c2_evaluated_solution_code_missing_or_mismatched"
    try:
        if _sha256(ast.unparse(ast.parse(code)).encode("utf-8")) != claim.code_anchor.get("canonical_ast_sha256"):
            return telemetry, "c2_evaluated_solution_ast_mismatch"
        selection = facts.get("interface_selection") or {}
        versions = [value for value in (candidate.get("template_version"), selection.get("template_version"),
                                         facts.get("template_version")) if value is not None]
        if any(value != "v2" for value in versions):
            return telemetry, "c2_solution_template_version_mismatch"
        modes = [value for value in (candidate.get("postprocess_mode"), selection.get("postprocess_mode"),
                                      facts.get("postprocess_mode")) if value is not None]
        if any(value not in ("none", "relocate_2opt") for value in modes) or len(set(modes)) > 1:
            return telemetry, "c2_solution_postprocess_mode_mismatch"
    except (KeyError, OSError, RecursionError, SyntaxError, TypeError, ValueError) as exc:
        return telemetry, f"c2_probe_error:{type(exc).__name__}"
    return screen_cvrp_c2_solution(
        code,
        template_id=scope["interface_id"],
        template_version="v2",
        postprocess_mode=modes[0] if modes else "none",
    )


def _geometry_scale_from_probes(probes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    sizes = [probe["size"] for probe in probes]
    return {
        **{target: sorted({probe[field] for probe in probes}) for target, field in zip(
            _GEOMETRY_FIELDS, ("spatial_mode", "demand_cv_mode", "depot_mode"), strict=True,
        )},
        "scale_range": [min(sizes), max(sizes)],
    }


def _replay_c2_screen(receipt: Any) -> tuple[dict[str, Any], str | None]:
    from agent_skill_loop.interface_design.multiscale import ONLINE_C2_JOINT_PROBES

    if not isinstance(receipt, list) or len(receipt) != 2 or not isinstance(receipt[0], dict):
        raise ValueError("auto_dream_c2_probe_receipts_invalid")
    telemetry, reason = receipt
    ratio = telemetry.get("c2_latency_ratio_max")
    expected_keys = {"c2_multiscale_screen_passed", "c2_latency_ratio_max", "c2_probe_budget_ms"}
    if reason is None:
        expected_keys.update((*_GEOMETRY_FIELDS, "scale_range"))
    if (telemetry.get("c2_multiscale_screen_passed") is not (reason is None)
            or telemetry.get("c2_probe_budget_ms") != _C2_BUDGET_MS
            or telemetry.keys() != expected_keys
            or (ratio is not None and (type(ratio) not in (float, int) or not math.isfinite(ratio) or ratio < 0))):
        raise ValueError("auto_dream_c2_probe_receipts_invalid")
    if reason is None:
        geometry = _geometry_scale_from_probes(ONLINE_C2_JOINT_PROBES)
        if ratio is None or ratio > _C2_RATIO_LIMIT or any(telemetry.get(key) != value for key, value in geometry.items()):
            raise ValueError("auto_dream_c2_probe_receipts_invalid")
    elif not isinstance(reason, str) or not re.fullmatch(r"[a-zA-Z0-9_:]{1,128}", reason):
        raise ValueError("auto_dream_c2_probe_receipts_invalid")
    return telemetry, reason


def _usage(receipt: Mapping[str, Any]) -> dict[str, int]:
    usage = receipt.get("usage")
    if not isinstance(usage, Mapping):
        raise ValueError("auto_dream_offline_token_accounting_required")
    counts = {key: usage.get(key) for key in ("input_tokens", "output_tokens")}
    if any(type(count) is not int or count < 0 for count in counts.values()) or not sum(counts.values()):
        raise ValueError("auto_dream_offline_token_accounting_required")
    return counts


def auto_dream(*, dev_artifacts: Sequence[Path], source_stores: Sequence[Path], output_store: Path,
               output_dir: Path, offline_llm_driver: Callable[[dict[str, Any]], Mapping[str, Any]] | None = None,
               require_c2_multiscale_admission: bool = False,
               ) -> dict[str, Any]:
    """Consolidate explicitly authorized dev claims into a staged memory store.

    Each artifact supplies ``split``, ``claims`` and inline or referenced
    evaluation facts. Claims select an exact source revision or carry an inline
    entry. An optional model may choose a representative per cluster by
    returning ``representative_claim_id``, ``claim_evidence_manifest`` and
    measured ``usage``. The resulting evidence and caveats are rendered by code.
    """
    if type(require_c2_multiscale_admission) is not bool:
        raise ValueError("auto_dream_c2_admission_flag_invalid")
    if not dev_artifacts:
        raise ValueError("auto_dream_dev_artifact_required")
    output_store, output_dir = _write_root(Path(output_store)), _write_root(Path(output_dir))
    lock_path = _write_root(output_dir / "auto_dream.lock")
    if require_c2_multiscale_admission:
        output_dir.mkdir(parents=True, exist_ok=True)
    # Freeze the timed C2 receipts and the publications under one writer. On an
    # interrupted promotion, replay the same measured timings and card identity.
    early_lock = (exclusive_file_lock(lock_path, busy="auto_dream_writer_busy")
                  if require_c2_multiscale_admission else nullcontext())
    with early_lock:
        return _consolidate(dev_artifacts, source_stores, output_store, output_dir,
                            offline_llm_driver, require_c2_multiscale_admission, lock_path)


def _consolidate(dev_artifacts: Sequence[Path], source_stores: Sequence[Path], output_store: Path, output_dir: Path,
                 offline_llm_driver: Callable[[dict[str, Any]], Mapping[str, Any]] | None,
                 require_c2_multiscale_admission: bool, lock_path: Path) -> dict[str, Any]:
    source_roots = [_read_path(Path(path)) for path in source_stores]
    sources = []
    for root in source_roots:
        if (not root.is_dir() or any(output.is_relative_to(root) or root.is_relative_to(output)
                                     for output in (output_store, output_dir))
                or next(root.glob("*/*.publish"), None) is not None):
            raise ValueError("auto_dream_source_store_invalid")
        sources.append(MemoryAPI(root, read_only=True))

    clusters = defaultdict(list)
    rejected = []
    receipt_path = _write_root(output_dir / "c2_probe_receipts.json") if require_c2_multiscale_admission else None
    receipt = None
    if receipt_path is not None and receipt_path.is_file():
        receipt = json.loads(receipt_path.read_bytes())
        if (not isinstance(receipt, dict) or receipt.get("schema_version") != _C2_RECEIPT_SCHEMA
                or not isinstance(receipt.get("screens"), dict)):
            raise ValueError("auto_dream_c2_probe_receipts_invalid")
    screened = {}
    inputs, seen_claims = set(), set()
    for artifact in dev_artifacts:
        doc, facts, digest, artifact_digest = _load_artifact(Path(artifact))
        manifest = ClaimEvidenceManifest.from_dict(doc)
        if artifact_digest in inputs:
            continue
        inputs.add(artifact_digest)
        raw_claims = {item["claim_id"]: item for item in doc["claims"]}
        for claim in manifest.claims:
            if claim.claim_id in seen_claims:
                raise ValueError("auto_dream_duplicate_claim_id")
            seen_claims.add(claim.claim_id)
            candidate = _match_evidence(claim, facts, digest)
            raw = raw_claims[claim.claim_id]
            try:
                entry, provenance = _entry(raw, claim, candidate, sources)
            except ValueError as exc:
                if not require_c2_multiscale_admission or str(exc) != "auto_dream_unverified_solution":
                    raise
                rejected.append({"claim_id": claim.claim_id, "source_reference": raw.get("source_reference"),
                                 "rejection_reason": str(exc), "c2_multiscale_screen_passed": False,
                                 "c2_latency_ratio_max": None, "c2_probe_budget_ms": _C2_BUDGET_MS})
                continue
            # Equality of canonical AST hashes is a conservative clustering
            # rule. Compare only cards with the same evaluator and interface,
            # and keep scope and memory kind exactly as they were verified.
            anchor = _candidate_ast(candidate) or claim.code_anchor.get("code_sha256")
            key = (_json(claim.applicability_scope), entry.type, anchor)
            geometry_scale = _geometry_scale_tags(facts, candidate, provenance)
            if entry.type == "solution" and require_c2_multiscale_admission:
                probe_key = evidence_digest({"evaluation_facts_sha256": digest, "evidence_ref": claim.evidence_ref,
                                             "scope_kind_anchor": key})
                if probe_key not in screened:
                    if receipt is None:
                        screened[probe_key] = _screen_c2_solution(claim, candidate, facts)
                    elif probe_key in receipt["screens"]:
                        screened[probe_key] = _replay_c2_screen(receipt["screens"][probe_key])
                    else:
                        raise ValueError("auto_dream_c2_probe_receipts_mismatch")
                telemetry, error = screened[probe_key]
                if error is not None:
                    rejected.append({"claim_id": claim.claim_id, "source_reference": raw.get("source_reference"),
                                     "rejection_reason": error, **telemetry})
                    continue
                geometry_scale.update(telemetry)
            clusters[key].append((claim, entry, raw.get("source_reference"), provenance, geometry_scale))

    publications = []
    totals = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
    for _, cluster in sorted(clusters.items()):
        cluster.sort(key=lambda row: row[0].claim_id)
        expected = ClaimEvidenceManifest(tuple(row[0] for row in cluster))
        manifest = expected.as_dict()
        chosen = cluster[0]
        if offline_llm_driver is not None:
            llm_receipt = offline_llm_driver({"claim_evidence_manifest": expected.as_dict(),
                                              "cards": [deepcopy(row[1].as_dict()) for row in cluster]})
            if not isinstance(llm_receipt, Mapping):
                raise ValueError("auto_dream_llm_receipt_invalid")
            _check_dev(llm_receipt)
            usage = _usage(llm_receipt)
            totals["calls"] += 1
            for key, count in usage.items():
                totals[key] += count
            ClaimEvidenceManifest.from_dict(llm_receipt.get("claim_evidence_manifest")).validate_preserves(expected)
            representative = llm_receipt.get("representative_claim_id")
            chosen = next((row for row in cluster if row[0].claim_id == representative), None)
            if chosen is None:
                raise ValueError("auto_dream_representative_claim_invalid")
        claim, card, _, source_provenance, geometry_scale = chosen
        source_refs = sorted({row[2] for row in cluster if row[2] is not None})
        source_bindings = {row[0].claim_id: row[2] for row in cluster}
        identity = evidence_digest({"manifest": manifest, "entry": card.as_dict(), "source_bindings": source_bindings})
        caveat_fields = ("claim_id", "denominators", "adverse_results", "contradictions")
        caveats = "\n".join(f"- {_json({key: item[key] for key in caveat_fields})}" for item in manifest["claims"])
        card = replace(card, name=f"dream-{identity[:32]}", body=f"{card.body.rstrip()}\n\n## Verified Dev Evidence\n{caveats}")
        _validate_entry(card)
        provenance = {key: source_provenance[key] for key in (
            "source_skill_ref", "source_evaluation_id", "candidate_code_sha256", "suite_hash", "evaluator_hash",
            "canonical_ast_sha256", "parent_version_id", "interface_id", "prefix_trace_equal",
        ) if key in source_provenance}
        provenance.update(evaluation_facts_sha256=claim.evaluation_facts_sha256, evidence_ref=claim.evidence_ref,
                          claim_evidence_manifest_sha256=evidence_digest(manifest), source_split="dev")
        provenance.update(geometry_scale)
        publications.append((identity, card, provenance, manifest, source_refs, source_bindings, geometry_scale))

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_root(output_store / ".writer.lock")
    late_lock = (nullcontext() if require_c2_multiscale_admission else
                 exclusive_file_lock(lock_path, busy="auto_dream_writer_busy"))
    with late_lock:
        manifest_path = _write_root(output_dir / "auto_dream_manifest.json")
        staging_path = _write_root(output_dir / "l3_promotion_candidates.json")
        receipt_sha = None
        if receipt_path is not None and screened:
            expected_receipt = {"schema_version": _C2_RECEIPT_SCHEMA, "dev_artifact_sha256": sorted(inputs),
                                "screens": screened}
            text = _json(expected_receipt) + "\n"
            if receipt is not None and _json(receipt) + "\n" != text:
                raise ValueError("auto_dream_c2_probe_receipts_mismatch")
            if receipt is None:
                _atomic_text(receipt_path, text)
            receipt_sha = _sha256(text.encode("utf-8"))
        elif receipt is not None:
            raise ValueError("auto_dream_c2_probe_receipts_mismatch")
        expected_refs = [f"{card.project}/{card.type}_{card.name}@v0001" for _, card, *_ in publications]
        if manifest_path.is_file():
            prior = json.loads(manifest_path.read_bytes())
            if (prior["dev_artifact_sha256"] != sorted(inputs) or
                    bool(prior.get("require_c2_multiscale_admission")) != require_c2_multiscale_admission):
                raise ValueError("auto_dream_batch_already_frozen")
            if require_c2_multiscale_admission:
                staging = json.loads(staging_path.read_bytes())
                api = MemoryAPI(output_store, read_only=True, json_only=True)
                if (staging.get("auto_dream_manifest_sha256") != _sha256(manifest_path.read_bytes())
                        or staging.get("candidates") != prior["cards"] or prior.get("c2_probe_receipts_sha256") != receipt_sha
                        or [item["reference"] for item in prior["cards"]] != expected_refs):
                    raise ValueError("auto_dream_frozen_batch_integrity_failed")
                for item in prior["cards"]:
                    card = api.read_version(item["reference"], require_active=True)
                    if any(card["provenance"].get(key) != value for key, value in item.get("geometry_scale", {}).items()):
                        raise ValueError("auto_dream_frozen_batch_integrity_failed")
                return prior
            if [item["reference"] for item in prior["cards"]] != expected_refs:
                raise ValueError("auto_dream_batch_already_frozen")
        api = MemoryAPI(output_store, json_only=require_c2_multiscale_admission)
        cards = []
        for identity, card, provenance, claims, source_refs, source_bindings, geometry_scale in publications:
            ref = api.write(card, format_version=3, provenance=provenance, operation_key=f"auto_dream:{identity}")["reference"]
            cards.append({"reference": ref, "source_references": source_refs, "source_bindings": source_bindings,
                          "claim_evidence_manifest": claims,
                          **({"geometry_scale": geometry_scale} if geometry_scale else {})})
        result = {"schema_version": "m35-auto-dream/v1", "source_split": "dev",
                  "dev_artifact_sha256": sorted(inputs), "cards": cards,
                  "offline_llm_usage": {**totals, "mode": "llm" if offline_llm_driver is not None else "deterministic",
                                        "total_tokens": totals["input_tokens"] + totals["output_tokens"]}}
        if require_c2_multiscale_admission:
            result.update(require_c2_multiscale_admission=True, rejected_candidates=sorted(
                rejected, key=lambda item: item["claim_id"],
            ))
            if receipt_sha is not None:
                result["c2_probe_receipts_sha256"] = receipt_sha
        staging = {"schema_version": "m35-l3-promotion-candidates/v1", "source_split": "dev", "activation": "staged",
                   "auto_dream_manifest_sha256": _sha256((_json(result) + "\n").encode("utf-8")), "candidates": cards}
        _atomic_text(staging_path, _json(staging) + "\n")
        _atomic_text(manifest_path, _json(result) + "\n")
    return result
