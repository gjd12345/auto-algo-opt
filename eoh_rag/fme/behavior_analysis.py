"""Prospective CVRP behavior forecasts and deterministic scoring helpers."""
from __future__ import annotations

import json
import math
from statistics import mean
from typing import Any, Iterable


def _finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _number(x: Any, low: float | None = None, high: float | None = None) -> float | None:
    if not _finite(x): return None
    x = float(x)
    if low is not None and x < low or high is not None and x > high: return None
    return x


def _panel(panel: Any) -> tuple[list[dict[str, Any]], list[str]]:
    states = panel.get("states", []) if isinstance(panel, dict) else panel if isinstance(panel, list) else []
    states = [x for x in states if isinstance(x, dict) and x.get("state_id") is not None]
    target = panel.get("targets", panel.get("families", [])) if isinstance(panel, dict) else []
    if isinstance(target, dict): target = list(target)
    ids = [str(x.get("family_id", x.get("id", x))) if isinstance(x, dict) else str(x) for x in target]
    return states, ids


def build_analysis_prompt(style: str, code: str, parent_summary: str, panel: Any,
                          target_descriptions: Any, previous_context: str = "") -> str:
    if style not in {"scalar", "passive", "grounded", "behavior_grounded", "B", "C"}: raise ValueError("unknown_analysis_style")
    grounded = style in {"grounded", "behavior_grounded", "C"}
    guide = ("Use ordinary concise passive mechanism reasoning." if not grounded else
             "Use behavior-grounded reasoning: explicitly state claim -> behavior -> condition, and quote an exact code substring in code_evidence.")
    return "\n".join((
        "CVRP prospective analysis. Candidate has not been executed; outcomes are hidden.", guide,
        "Return exactly one JSON object with explanation, predicted_effect, predicted_success_probability, behavior_predictions, targeted_predictions, next_edit, code_evidence.",
        "predicted_effect is (parent_cost-candidate_cost)/abs(parent_cost), a finite JSON number <=1 with no lower bound (0.02=2%; -2=-200%). predicted_success_probability is the probability of strictly positive ordinary development improvement, in [0,1].",
        "behavior_predictions is an object mapping each state_id to its predicted integer return. unvisited_nodes already excludes visited and capacity-infeasible customers; depot 0 may be returned. Predict THIS code, not a preferred or optimal action.",
        "targeted_predictions is an object mapping EACH target family to {failure_probability: number in [0,1], predicted_effect: relative fraction <=1}. Failure means invalid runtime OR relative gain < -1e-9 against the supplied parent; ties are NOT failures. Predict the family's mean objective, not one case.",
        "next_edit is {instruction: short code edit, probe_id: one supplied state_id, expected_node: integer returned by the proposed edited child ON THAT SAME STATE, target_family: one supplied family ID}. Predict an edit likely to improve that family. Keep explanation under 120 words. code_evidence is an exact contiguous code substring; passive analysis may leave it empty. Grounded explanation must contain the labels claim, behavior, condition; these labels alone do not verify the claim.",
        f"CODE:\n{code}", f"PARENT SCALAR SUMMARY:\n{parent_summary}",
        f"FIXED NUMERIC STATES (results hidden):\n{json.dumps(panel, ensure_ascii=False, sort_keys=True)}",
        f"TARGET FAMILY DESCRIPTIONS (outcomes hidden):\n{json.dumps(target_descriptions, ensure_ascii=False, sort_keys=True)}",
        f"Previous context (not observed target results):\n{previous_context or '(none)'}"))


def _parse_json(text: str) -> dict[str, Any] | None:
    value = str(text or "").strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[1] if "\n" in value else ""
        value = value.rsplit("```", 1)[0]
    try: value = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError): return None
    return value if isinstance(value, dict) else None


def parse_forecast(text: str, panel: Any, target_ids: Iterable[str], code: str, style: str) -> dict[str, Any]:
    states, panel_targets = _panel(panel); families = [str(x) for x in target_ids] or panel_targets
    state_ids = [str(x["state_id"]) for x in states]
    allowed = {str(x["state_id"]): set(x["unvisited_nodes"]) | {0} for x in states}
    errors: list[str] = []; raw = _parse_json(text)
    if raw is None: raw = {}; errors.append("invalid_json_object")
    effect, probability = _number(raw.get("predicted_effect"),high=1), _number(raw.get("predicted_success_probability"), 0, 1)
    if effect is None: errors.append("predicted_effect_invalid")
    if probability is None: errors.append("predicted_success_probability_invalid")
    source = raw.get("behavior_predictions") if isinstance(raw.get("behavior_predictions"), dict) else {}
    behavior: dict[str, int | None] = {}
    for sid in state_ids:
        value = source.get(sid); good = isinstance(value, int) and not isinstance(value, bool) and (not allowed[sid] or value in allowed[sid])
        behavior[sid] = value if good else None
        if not good: errors.append(f"behavior_prediction_invalid:{sid}")
    source = raw.get("targeted_predictions") if isinstance(raw.get("targeted_predictions"), dict) else {}
    targeted: dict[str, dict[str, float | None]] = {}
    for family in families:
        item = source.get(family) if isinstance(source.get(family), dict) else {}
        fp, pe = _number(item.get("failure_probability"), 0, 1), _number(item.get("predicted_effect"),high=1)
        targeted[family] = {"failure_probability": fp, "predicted_effect": pe}
        if fp is None: errors.append(f"failure_probability_invalid:{family}")
        if pe is None: errors.append(f"targeted_effect_invalid:{family}")
    nxt = raw.get("next_edit") if isinstance(raw.get("next_edit"), dict) else {}; expected = nxt.get("expected_node")
    expected_good = isinstance(expected, int) and not isinstance(expected, bool) and expected in allowed.get(str(nxt.get('probe_id')),set())
    next_edit = {k: nxt.get(k) for k in ("instruction", "probe_id", "expected_node", "target_family")}
    if not isinstance(nxt.get("instruction"), str) or not nxt["instruction"].strip(): errors.append("next_edit_instruction_invalid")
    if str(nxt.get("probe_id")) not in state_ids: errors.append("next_edit_probe_id_invalid")
    if not expected_good: errors.append("next_edit_expected_node_invalid")
    if str(nxt.get("target_family")) not in families: errors.append("next_edit_target_family_invalid")
    explanation = raw.get("explanation") if isinstance(raw.get("explanation"), str) else ""
    if not explanation.strip(): errors.append("explanation_missing")
    evidence = raw.get("code_evidence") if isinstance(raw.get("code_evidence"), str) else ""; reference = bool(evidence.strip() and evidence in code)
    grounded = style in {"grounded", "behavior_grounded", "C"}; grounding = not grounded or (reference and all(x in explanation.lower() for x in ("claim", "behavior", "condition")))
    if grounded and not grounding: errors.append("grounding_link_invalid")
    fields = {"explanation": explanation, "predicted_effect": effect, "predicted_success_probability": probability,
              "behavior_predictions": behavior, "behavior_families": {str(x["state_id"]): str(x['family']) for x in states},
              "targeted_predictions": targeted, "next_edit": next_edit, "code_evidence": evidence}
    return {"valid": not errors, "errors": errors, "fields": fields, "code_reference_valid": reference, "grounding_compliant": grounding}


def forecast_outcomes(forecast: dict[str, Any], behavior_result: Any, target_results: Any,
                      parent_target_results: Any, epsilon: float = 1e-9) -> dict[str, list[dict[str, Any]]]:
    fields = forecast.get("fields", {}) if isinstance(forecast, dict) else {}; choices = behavior_result.get("choices", {}) if isinstance(behavior_result, dict) else {}; states = behavior_result.get("state_results", {}) if isinstance(behavior_result, dict) else {}
    if isinstance(states,list): states={r['state_id']:r for r in states}
    behavior = []
    for sid, predicted in (fields.get("behavior_predictions", {}) or {}).items():
        observed = states.get(sid, {}) if isinstance(states, dict) else {}; actual = choices.get(sid, observed.get("choice", observed.get("node"))) if isinstance(observed, dict) else choices.get(sid)
        valid = bool(observed.get("valid_execution", observed.get("valid", actual is not None))) if isinstance(observed, dict) else actual is not None
        behavior.append({"family": (fields.get("behavior_families", {}) or {}).get(sid, "behavior"), "state_id": sid, "correct": bool(valid and predicted is not None and predicted == actual), "predicted": predicted, "actual": actual, "valid_execution": valid})
    targeted = []
    for family, prediction in (fields.get("targeted_predictions", {}) or {}).items():
        observed = target_results.get(family) if isinstance(target_results, dict) else None; parent = parent_target_results.get(family) if isinstance(parent_target_results, dict) else None
        if isinstance(observed, dict): valid, objective = bool(observed.get("valid", True)), observed.get("objective", observed.get("candidate_objective"))
        else: valid, objective = observed is not None, observed
        parent_obj = parent.get("objective", parent.get("parent_objective")) if isinstance(parent, dict) else parent
        parent_valid=isinstance(parent,dict) and parent.get('valid') is True and _finite(parent_obj)
        gain = ((float(parent_obj) - float(objective)) / max(abs(float(parent_obj)), epsilon) if parent_valid and valid and _finite(objective) else None)
        # 无有效父算法参照时不能把“无法比较”伪标为失败；保留缺失标签。
        failure = 1 if not valid else int(gain < -epsilon) if gain is not None else None
        probability = prediction.get("failure_probability") if isinstance(prediction, dict) else None
        targeted.append({"family": family, "probability": probability, "actual_failure": failure, "actual_gain": gain, "predicted_effect": prediction.get("predicted_effect") if isinstance(prediction, dict) else None, "brier": 1.0 if probability is None or failure is None else (float(probability) - failure) ** 2, "prediction_missing": probability is None, 'reference_missing':not parent_valid})
    return {"behavior": behavior, "targeted": targeted}


def _auc(rows: list[tuple[float, int]]) -> float | None:
    pos = [p for p, y in rows if y == 1]; neg = [p for p, y in rows if y == 0]
    if not pos or not neg: return None
    return sum(1 if p > n else .5 if p == n else 0 for p in pos for n in neg) / (len(pos) * len(neg))


def metrics(rows: dict[str, list[dict[str, Any]]], *, calibration_bins: int = 5) -> dict[str, Any]:
    behavior, target = rows.get("behavior", []), rows.get("targeted", []); valid = [r for r in behavior if r.get("valid_execution")]
    itt = mean(bool(r.get("correct")) for r in behavior) if behavior else None; conditional = mean(bool(r.get("correct")) for r in valid) if valid else None
    families = {r.get("family", "behavior") for r in behavior}; macro = mean(mean(bool(r.get("correct")) for r in behavior if r.get("family", "behavior") == f) for f in families) if families else None
    probs = [(float(r["probability"]), int(r["actual_failure"])) for r in target if _finite(r.get("probability")) and r.get('actual_failure') is not None]; labels = [y for _, y in probs]; pos, neg = labels.count(1), labels.count(0); eligible = pos >= 10 and neg >= 10
    tpr = sum(p >= .5 and y == 1 for p, y in probs) / pos if pos else None; tnr = sum(p < .5 and y == 0 for p, y in probs) / neg if neg else None
    bins = []
    if eligible:
        for i in range(calibration_bins):
            sub = [(p, y) for p, y in probs if i / calibration_bins <= p < (i + 1) / calibration_bins or i == calibration_bins - 1 and p == 1]
            if sub: bins.append({"bin": i, "count": len(sub), "mean_probability": mean(p for p, _ in sub), "observed_rate": mean(y for _, y in sub)})
    ece = sum(x["count"] / len(probs) * abs(x["mean_probability"] - x["observed_rate"]) for x in bins) if bins else None
    target_families={r['family'] for r in target}
    target_macro=mean(mean(float(r['brier']) for r in target if r['family']==f) for f in target_families) if target_families else None
    return {"behavior_itt_accuracy": itt, "behavior_conditional_accuracy": conditional, "behavior_macro_accuracy": macro,
            "target_macro_brier":target_macro,
            "target_brier_itt": mean(float(r.get("brier", 1.0)) for r in target) if target else None, "target_brier_conditional": mean((p-y) ** 2 for p, y in probs) if probs else None,
            "prediction_coverage": {"behavior": sum(r.get('predicted') is not None for r in behavior) / len(behavior) if behavior else 0.0, "target": len(probs) / len(target) if target else 0.0},
            "behavior_execution_coverage":len(valid)/len(behavior) if behavior else 0.0,
            "target_label_coverage":sum(r.get('actual_failure') is not None for r in target)/len(target) if target else 0.0,
            "balanced_accuracy": (tpr + tnr) / 2 if eligible else None, "roc_auc": _auc(probs) if eligible else None, "calibration_bins": bins if eligible else None, "ece": ece if eligible else None,
            "baselines": {"always_failure_brier": mean((1-y) ** 2 for _, y in probs) if probs else None, "always_no_failure_brier": mean(y ** 2 for _, y in probs) if probs else None, "constant_half_brier": mean((.5-y) ** 2 for _, y in probs) if probs else None},
            "counts": {"behavior": len(behavior), "behavior_valid": len(valid), "target": len(target), "target_probability_valid": len(probs), "target_positive": pos, "target_negative": neg}}


__all__ = ["build_analysis_prompt", "parse_forecast", "forecast_outcomes", "metrics"]
