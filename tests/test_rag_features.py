from __future__ import annotations

import pytest

from eoh_rag.rag.features import (
    STRATEGY_FEATURES,
    extract_code_features,
    extract_identifier_tokens,
    extract_strategy_features,
    normalize_strategy_feature,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("clustering", "cluster"),
        ("best-fit", "best_fit"),
        ("bestFit", "best_fit"),
        ("2opt", "two_opt"),
        ("regret2", "regret"),
        ("look_ahead", "lookahead"),
        ("not-a-strategy", None),
    ],
)
def test_normalize_strategy_feature_aliases(raw: str, expected: str | None) -> None:
    assert normalize_strategy_feature(raw) == expected


def test_normalization_is_idempotent_for_canonical_features() -> None:
    for feature in STRATEGY_FEATURES:
        assert normalize_strategy_feature(feature) == feature
        assert normalize_strategy_feature(normalize_strategy_feature(feature)) == feature


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("regret_score = second_best - best", {"regret"}),
        ("far_first = distant_nodes[0]", {"farthest"}),
        ("choice = argmin(min_dist)", {"nearest"}),
        ("clarke_wright_savings = saving", {"savings"}),
        ("rest_capacity = cap - demand", {"capacity"}),
        ("remaining_capacity = capacity - used; slack = remaining_capacity", {"residual"}),
        ("score = bestFit(item)", {"best_fit"}),
        ("labels = kmeans_clustering(points)", {"cluster"}),
        ("look_ahead = two_step_score(node)", {"lookahead"}),
    ],
)
def test_extract_strategy_features_maps_strong_patterns(code: str, expected: set[str]) -> None:
    assert expected <= extract_strategy_features(code)


@pytest.mark.parametrize(
    "code",
    [
        "return value",
        "if feasible: return candidate",
        "future = value",
        "alpha = 0.5; beta = 0.2; gamma = 0.3",
        "demand = demands[node]",
        "distance = distance_matrix[current][node]",
        "capacity = rest",
        "destination = depot",
    ],
)
def test_weak_or_api_tokens_do_not_trigger_strategy_features(code: str) -> None:
    assert extract_strategy_features(code) == set()


def test_compound_api_terms_can_trigger_canonical_features() -> None:
    features = extract_strategy_features(
        "distance_penalty = nearest_distance; depot_distance = return_distance; "
        "capacity_utilization = remaining_vehicle_capacity"
    )
    assert {"distance", "penalty", "nearest", "depot", "destination", "capacity", "utilization"} <= features


def test_strategy_extractor_returns_only_canonical_features() -> None:
    features = extract_strategy_features(
        "best = delta + candidate_value; regret_score = second_best; forward_score = threshold"
    )
    assert features <= STRATEGY_FEATURES
    assert not {"best", "delta", "candidate", "value", "forward_score", "threshold"} & features


def test_identifier_and_legacy_code_extractors_keep_existing_token_semantics() -> None:
    code = "func scoreCandidate(regretScore float64, capacity float64) { return regretScore }"
    assert extract_identifier_tokens(code) == extract_code_features(code)
    assert "regret" in extract_code_features(code)
    assert "capacity" not in extract_code_features(code)
