"""Deterministic M3.5 admission, diversity ranking and scoped cooldown."""

from __future__ import annotations

import ast
import hashlib
import json
import math
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from agent_skill_loop.evidence.search_progress import OBJECTIVE_PRECISION_FLOOR
from agent_skill_loop.file_lock import exclusive_file_lock
from agent_skill_loop.memory.api import _atomic_text, memory_is_active
from agent_skill_loop.memory.problem_vocab import problem_family, validate_problem_vocab


SCOPE_FIELDS = ("problem", "interface_id", "fleet_policy", "evaluator_version")
MAX_PACK_CARDS = 3
_TOKENS = re.compile(r"[^\W_]+")
_CODE_BLOCK = re.compile(r"```(?:python|py)?[ \t]*\r?\n(.*?)```", re.DOTALL | re.IGNORECASE)
_LEDGER_SCHEMA = "m35-cooldown/v1"
_INFRA_FAILURE = re.compile(
    r"429|rate[ _-]?limit|provider|connectivity|http[ _-]?(?:error|[45]\d\d)|transport|"
    r"no[ _-]?(?:result|evaluation)|unevaluated|crash|killed[ _-]?unknown|"
    r"interrupt|timeout|worker[ _-]?protocol|request[ _-]?deadline|evidence[ _-]?storage",
    re.IGNORECASE,
)


def _tokens(text: str) -> frozenset[str]:
    return frozenset(_TOKENS.findall(text.casefold()))


def ast_signature(code: str) -> frozenset[str]:
    """Use structural edge and operator tokens without running card code."""
    try:
        tree = ast.parse(code)
    except (SyntaxError, TypeError, ValueError, RecursionError):
        return frozenset()
    features = set()
    for node in ast.walk(tree):
        kind = type(node).__name__
        features.add(kind)
        features.update(f"{kind}>{type(child).__name__}" for child in ast.iter_child_nodes(node))
        if isinstance(node, ast.Attribute):
            features.add(f"attribute:{node.attr}")
    return frozenset(features)


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    return len(left & right) / len(left | right) if left or right else 0.0


def _family(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return problem_family(value.split("/", 1)[0])


def admission_allowed(card: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
    """Keep offline packing and unproven prefix behavior out of online OBP."""
    target = context.get("problem")
    if not isinstance(target, str) or not target:
        return False
    try:
        active = memory_is_active(card, context)
    except (TypeError, ValueError):
        return False
    if not active:
        return False
    family = _family(target)
    # Provenance and evidence carry evaluator observations in Sidecar cards
    # and offline artifacts, respectively. Card prose cannot establish a pass.
    sources = [card]
    for key in ("applicability_scope", "provenance", "evidence", "diagnostics"):
        value = card.get(key)
        if isinstance(value, Mapping):
            sources.append(value)
    source_families = {_family(source.get(key)) for source in sources
                       for key in ("problem", "project", "problem_family", "protocol_id")}
    source_families.discard(None)
    if family and source_families - {family}:
        return False
    if family != "online_obp":
        return True
    if source_families != {family}:
        return False
    prefix = [source["prefix_trace_equal"] for source in sources if "prefix_trace_equal" in source]
    if not prefix or not all(value is True or value == "true" for value in prefix):
        return False
    for source in sources:
        for key in ("future_lookahead", "uses_future_items", "prefix_invariance_violation"):
            if key in source and source[key] is not False and source[key] != "false":
                return False
    try:
        validate_problem_vocab(target, *(card[key] for key in ("name", "description", "body", "code")
                                        if isinstance(card.get(key), str)))
    except ValueError:
        return False
    return True


def _document(card: Mapping[str, Any]) -> str:
    return " ".join(card[key] for key in ("name", "description", "scene", "body")
                    if isinstance(card.get(key), str))


def _structure(card: Mapping[str, Any]) -> frozenset[str]:
    code = card.get("code")
    if isinstance(code, str) and (signature := ast_signature(code)):
        return signature
    body = card.get("body")
    if not isinstance(body, str):
        return frozenset()
    return frozenset().union(*(ast_signature(block) for block in _CODE_BLOCK.findall(body)))


def _ast_digest(card: Mapping[str, Any]) -> str | None:
    for key in ("code_anchor", "provenance"):
        values = card.get(key)
        if isinstance(values, Mapping):
            digest = values.get("canonical_ast_sha256")
            if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest):
                return digest
    return None


def rerank_mmr(
    query: str,
    candidates: Iterable[Mapping[str, Any]],
    *,
    context: Mapping[str, Any],
    mmr_lambda: float = 0.7,
    max_solution_cards: int = 1,
    ledger: CooldownLedger | None = None,
    round_id: int = 1,
) -> list[Mapping[str, Any]]:
    """Greedily maximize relevance minus redundancy with lexical tie breaks."""
    if type(mmr_lambda) not in (int, float) or not 0 <= mmr_lambda <= 1:
        raise ValueError("memory_mmr_lambda_invalid")
    if type(max_solution_cards) is not int or not 0 <= max_solution_cards <= MAX_PACK_CARDS:
        raise ValueError("memory_max_solution_cards_invalid")
    _validate_round(round_id)
    query_terms = _tokens(query)
    remaining = {}
    blocked = ledger.active_references(context, round_id) if ledger is not None else set()
    for card in candidates:
        reference = card.get("reference")
        if not isinstance(reference, str) or not reference or reference in remaining or reference in blocked:
            continue
        if card.get("type") not in {"insight", "antipattern", "solution"} or not admission_allowed(card, context):
            continue
        terms = _tokens(_document(card))
        relevance = len(query_terms & terms) / len(query_terms) if query_terms else 0.0
        remaining[reference] = (card, relevance, terms, _structure(card), _ast_digest(card))

    def similarity(left, right):
        if left[4] is not None and left[4] == right[4]:
            return 1.0
        if left[3] and right[3]:
            return jaccard(left[3], right[3])
        return jaccard(left[2], right[2])

    selected = []
    solution_count = 0
    while remaining and len(selected) < MAX_PACK_CARDS:
        eligible = [ref for ref, item in remaining.items()
                    if item[0]["type"] != "solution" or solution_count < max_solution_cards]
        if not eligible:
            break

        def score(ref):
            item = remaining[ref]
            redundancy = max((similarity(item, prior) for prior in selected), default=0.0)
            return (-(mmr_lambda * item[1] - (1 - mmr_lambda) * redundancy), -item[1], ref)

        chosen = remaining.pop(min(eligible, key=score))
        selected.append(chosen)
        solution_count += chosen[0]["type"] == "solution"
    return [item[0] for item in selected]


def _validate_round(round_id: int) -> None:
    if type(round_id) is not int or round_id < 1:
        raise ValueError("memory_cooldown_round_invalid")


def _identity(context: Mapping[str, Any]) -> tuple[str, str, str, str]:
    problem, interface, fleet, evaluator = (context.get(key) for key in SCOPE_FIELDS)
    result = (problem, interface, fleet, evaluator)
    if not all(isinstance(value, str) and value.strip() for value in result):
        raise ValueError("memory_cooldown_scope_invalid")
    return result


def _solver_evaluation(evaluation: Mapping[str, Any]) -> bool:
    if not isinstance(evaluation.get("evaluation_id"), str) or not evaluation["evaluation_id"].strip():
        return False
    if evaluation.get("solver_evaluated") is False or any(
        evaluation.get(key) is True for key in ("provider_failed", "provider_failure", "unevaluated_crash")
    ):
        return False
    for key in ("http_status", "delivery_http_status", "status_code"):
        status = evaluation.get(key)
        if status is not None and (type(status) is not int or not 200 <= status < 300):
            return False
    return not any(_INFRA_FAILURE.search(str(evaluation.get(key, "")))
                   for key in ("state", "status", "error_code", "terminal_reason", "failure_type"))


def _bound_execution_delta(root: Path, facts: Mapping[str, Any]) -> Mapping[str, Any]:
    binding = facts.get("execution_delta")
    if binding is None:
        return {}
    if not isinstance(binding, Mapping) or not isinstance(binding.get("ref"), str):
        raise ValueError("memory_execution_delta_binding_invalid")
    path = (root / binding["ref"]).resolve()
    if not path.is_relative_to(root):
        raise ValueError("memory_execution_delta_reference_invalid")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != binding.get("sha256"):
        raise ValueError("memory_execution_delta_hash_mismatch")
    result = json.loads(data)
    if not isinstance(result, dict) or result.get("schema_version") != "algorithm-optimization-execution-delta/v1":
        raise ValueError("memory_execution_delta_invalid")
    return result


def _checkpoint_request_ids(
    path: Path | None, run_id: str | None, request_ids: set[str],
) -> dict[tuple[str, str], str]:
    if path is None or not run_id or not path.is_file() or not request_ids:
        return {}
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as con:
        if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='candidate_provenance'").fetchone() is None:
            return {}
        rows = con.execute(
            "SELECT eval_id, code_sha256, physical_request_id FROM candidate_provenance "
            "WHERE run_id=? AND generation_status IN ('valid_candidate', 'invalid_candidate')",
            (run_id,),
        ).fetchall()
    by_candidate: dict[tuple[str, str], set[str]] = {}
    for eval_id, code_sha, request_id in rows:
        if request_id in request_ids and eval_id and code_sha:
            by_candidate.setdefault((eval_id, code_sha), set()).add(request_id)
    return {identity: next(iter(ids)) for identity, ids in by_candidate.items() if len(ids) == 1}


def _evaluation_identity(item: Mapping[str, Any]) -> tuple[str | None, str | None]:
    return item.get("evaluation_id"), item.get("code_sha256")


def _verified_score(candidate: Mapping[str, Any], suite_hash: str) -> tuple[float, int] | None:
    if candidate.get("valid") is not True or candidate.get("suite_hash") != suite_hash:
        return None
    objective, values = candidate.get("objective"), candidate.get("instance_objectives")
    if (type(objective) not in (float, int) or not math.isfinite(objective) or not isinstance(values, list)
            or not values or not all(type(value) in (float, int) and math.isfinite(value) for value in values)):
        return None
    return float(objective), len(values)


def iter_attributed_outcomes(
    session_dir: Path,
    facts: Mapping[str, Any],
    consumption: Mapping[str, Any],
    *,
    request_ledger: Path | None = None,
    request_run_id: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Join verified Session solver attempts to their delivered context receipts."""
    if facts.get("round_id") != consumption.get("round_id") or consumption.get("memory_enabled") is not True:
        return
    gateways = {}
    for receipt in consumption.get("gateway_requests", []):
        status = receipt.get("delivery_http_status")
        request_id = receipt.get("request_id")
        if (isinstance(request_id, str) and receipt.get("request_state") == "complete"
                and receipt.get("transport_status") == "delivered" and type(status) is int and 200 <= status < 300
                and receipt.get("context_status") == "gateway_attempt_exact_context"):
            gateways[request_id] = receipt
    if not gateways:
        return
    by_sequence = {receipt["sequence"]: receipt for receipt in gateways.values() if type(receipt.get("sequence")) is int}
    delta = _bound_execution_delta(Path(session_dir).resolve(), facts)
    by_candidate = {_evaluation_identity(item): item for item in delta.get("candidates", [])}
    by_checkpoint = _checkpoint_request_ids(request_ledger, request_run_id, set(gateways))
    attempts = {_evaluation_identity(item): item for item in facts.get("solver_attempts", [])}
    compiled = {item["reference"]: (item.get("body_sha256"), item.get("injected_sha256"))
                for item in consumption.get("compiled", []) if item.get("status") == "compiled_into_context"}
    candidates = facts.get("candidates", [])
    suite_hash, direction = facts.get("suite_hash"), facts.get("objective_direction")
    baseline = facts.get("baseline") or {}
    # A persisted incumbent from another template is not a comparable score.
    # Prefer it only if the same code was re-evaluated in this round.
    incumbent_hash = (facts.get("incumbent_before") or {}).get("code_sha256")
    if incumbent_hash:
        incumbent = next((item for item in candidates if item.get("code_sha256") == incumbent_hash
                          and item.get("origin") in {"baseline", "explicit_parent", "inherited_population"}
                          and _verified_score(item, suite_hash) is not None), None)
        if incumbent is not None:
            baseline = incumbent
    reference_score = _verified_score(baseline, suite_hash) if suite_hash else None

    for candidate in candidates:
        origin = candidate.get("origin")
        if origin not in {"generated", "generated_repair"} or type(candidate.get("valid")) is not bool:
            continue
        identity = _evaluation_identity(candidate)
        observed = attempts.get(identity)
        if (not observed or observed.get("origin") != origin
                or observed.get("state") != ("complete" if candidate["valid"] else "failed")
                or observed.get("valid") != int(candidate["valid"]) or observed.get("objective") != candidate.get("objective")
                or observed.get("error_code") != candidate.get("error_code")
                or candidate.get("completed") is False or not _solver_evaluation(candidate)):
            continue
        detail = by_candidate.get(identity, {})
        sequence = detail.get("request_index")
        if origin == "generated_repair":
            ref = candidate.get("repair_request_ref")
            match = re.fullmatch(r"request_(\d+)\.json", Path(ref).name) if isinstance(ref, str) else None
            sequence = int(match[1]) if match else None
        direct = by_sequence.get(sequence)
        checkpoint = gateways.get(by_checkpoint.get(identity))
        if direct is not None and checkpoint is not None and direct != checkpoint:
            continue
        gateway = direct or checkpoint
        purpose = "eoh_repair" if origin == "generated_repair" else "eoh_generation"
        if gateway is None or gateway.get("purpose") != purpose:
            continue
        attributed = sorted({item["reference"] for item in gateway.get("memory", [])
                             if item.get("status") == "gateway_attempt"
                             and item.get("reference") in compiled
                             and compiled[item["reference"]] == (item.get("body_sha256"), item.get("injected_sha256"))})
        if not attributed:
            continue
        score = _verified_score(candidate, suite_hash) if suite_hash else None
        improvement = regression = False
        if score is not None and reference_score is not None and score[1] == reference_score[1]:
            if direction in {"minimize", "maximize"}:
                delta_score = reference_score[0] - score[0] if direction == "minimize" else score[0] - reference_score[0]
                improvement = delta_score > OBJECTIVE_PRECISION_FLOOR
                regression = delta_score < -OBJECTIVE_PRECISION_FLOOR
        yield {
            "evaluation_id": identity[0], "code_sha256": identity[1], "problem": facts.get("problem"),
            "evaluator_version": facts.get("evaluator_hash"),
            "solver_evaluated": True, "completed": True, "valid": candidate["valid"],
            "error_code": candidate.get("error_code"), "http_status": gateway["delivery_http_status"],
            "attributed_references": attributed, "verified_improvement": improvement,
            "verified_metric_regression": regression, "request_id": gateway["request_id"],
            **{key: candidate[key] for key in ("evidence", "diagnostics", "protocol_id", "prefix_trace_equal")
               if key in candidate},
        }


class CooldownLedger:
    """Persist a round-based hold on each exact card/environment pair."""

    def __init__(self, path: Path | str, *, cooldown_rounds: int = 2) -> None:
        if type(cooldown_rounds) is not int or cooldown_rounds < 0:
            raise ValueError("memory_cooldown_rounds_invalid")
        self.path = Path(path).resolve()
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")
        self.cooldown_rounds = cooldown_rounds

    def _read(self) -> list[dict[str, Any]]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        if not isinstance(value, dict) or value.get("schema") != _LEDGER_SCHEMA or not isinstance(value.get("entries"), list):
            raise ValueError("memory_cooldown_ledger_invalid")
        return value["entries"]

    def active_references(self, context: Mapping[str, Any], round_id: int) -> set[str]:
        _validate_round(round_id)
        scope = list(_identity(context))
        return {entry["reference"] for entry in self._read() if entry["scope"] == scope
                and entry["observed_round"] < round_id <= entry["blocked_through_round"]}

    def is_active(self, reference: str, context: Mapping[str, Any], round_id: int) -> bool:
        return reference in self.active_references(context, round_id)

    def observe(
        self, reference: str, context: Mapping[str, Any], *, round_id: int, evaluation: Mapping[str, Any],
    ) -> bool:
        """Apply an attributable invalid solve or verified regression/re-entry.

        An attributable evaluation has its own evaluation ID and a list of
        card refs linked to that evaluated request by the runtime. Newer rounds
        supersede older ones. Within a round a verified improvement wins over
        a negative observation so retry order cannot reinstate a cleared hold.
        """
        if not isinstance(reference, str) or not reference:
            raise ValueError("memory_cooldown_reference_invalid")
        _validate_round(round_id)
        scope = list(_identity(context))
        attributed = evaluation.get("attributed_references")
        if (not isinstance(attributed, (list, tuple, set, frozenset)) or reference not in attributed
                or not _solver_evaluation(evaluation)
                or any(key in evaluation and evaluation[key] != context.get(key) for key in SCOPE_FIELDS)
                or not admission_allowed(evaluation, context)):
            return False
        completed, valid = evaluation.get("completed"), evaluation.get("valid")
        improvement = evaluation.get("verified_improvement") is True
        regression = evaluation.get("verified_metric_regression") is True
        if improvement and regression:
            return False
        if improvement:
            if completed is not True or valid is not True:
                return False
            outcome = "verified_improvement"
        elif regression and completed is not False and valid is not False:
            outcome = "verified_metric_regression"
        elif completed is True and valid is False:
            outcome = "invalid_solver_result"
        else:
            return False

        def order(entry):
            return (entry["observed_round"], entry["outcome"] == "verified_improvement", entry["evaluation_id"])

        new_entry = {"reference": reference, "scope": scope, "observed_round": round_id,
                     "evaluation_id": evaluation["evaluation_id"], "outcome": outcome,
                     "blocked_through_round": round_id if improvement else round_id + self.cooldown_rounds}
        with exclusive_file_lock(self.lock_path, busy="memory_cooldown_writer_busy"):
            entries = self._read()
            for index, entry in enumerate(entries):
                if entry["reference"] == reference and entry["scope"] == scope:
                    if order(new_entry) <= order(entry):
                        return False
                    entries[index] = new_entry
                    break
            else:
                entries.append(new_entry)
            entries.sort(key=lambda entry: (entry["reference"], entry["scope"]))
            _atomic_text(self.path, json.dumps({"schema": _LEDGER_SCHEMA, "entries": entries},
                                               sort_keys=True, indent=2) + "\n")
        return True


def regime_false_trigger_rate(events: Iterable[Mapping[str, Any]], regime: Any) -> dict[str, Any]:
    """Measure cooldown false triggers on completed, valid held-out cases."""
    samples = [event for event in events if event.get("regime") == regime and event.get("held_out") is True
               and event.get("completed") is True and event.get("valid") is True
               and type(event.get("triggered")) is bool]
    false_triggers = sum(event["triggered"] for event in samples)
    return {"regime": regime, "sample_count": len(samples), "false_triggers": false_triggers,
            "status": "ok" if len(samples) >= 3 else "insufficient_evidence",
            "rate": false_triggers / len(samples) if len(samples) >= 3 else None}
