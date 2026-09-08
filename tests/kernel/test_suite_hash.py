from __future__ import annotations

import json

from agent_skill_loop.contracts import DEFAULT_SEED
from agent_skill_loop.problems.cvrp import build_suite, suite_hash


def test_suite_hash_stable_across_rebuild_and_reload():
    first = build_suite(DEFAULT_SEED, split="dev_train", count=3, size=20)
    second = build_suite(DEFAULT_SEED, split="dev_train", count=3, size=20)
    assert first["content_hash"] == second["content_hash"]
    dumped = json.loads(json.dumps(first))
    assert dumped["content_hash"] == suite_hash(dumped["problem"], dumped["split"], dumped["instances"])
    assert dumped["content_hash"] == first["content_hash"]


def test_suite_hash_changes_when_instances_change():
    suite = build_suite(DEFAULT_SEED, split="dev_train", count=3, size=20)
    mutated = json.loads(json.dumps(suite))
    mutated["instances"][0]["demands"][0] = mutated["instances"][0]["demands"][0] + 1
    assert suite_hash(mutated["problem"], mutated["split"], mutated["instances"]) != suite["content_hash"]
