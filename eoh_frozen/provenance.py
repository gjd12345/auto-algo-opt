"""Parent-side provenance adapters for the pinned official EoH engine.

The official evaluator runs in a fresh spawned process.  Provenance therefore
cannot be inferred from mutable counters stored on ``FrozenProblem``: every
child receives its own copy of those counters.  These small adapters bind
identity before the official call and clear seed bindings after seed
initialisation, while leaving EoH selection, operators, and population
management untouched.
"""

from __future__ import annotations

import hashlib
import threading
import uuid
from typing import Any

from eoh.eoh.eoh import EOH


class SeedAwareEOH(EOH):
    """Clear code-bound seed provenance after official seed initialisation."""

    def _init_population(self, t0):
        try:
            return super()._init_population(t0)
        finally:
            clear = getattr(self.problem, "clear_seed_bindings", None)
            if callable(clear):
                clear()

    def _build_with_parent_evidence(self, population_snapshot, operator, context):
        """Observe upstream's selected parents without choosing or editing them.

        The pinned EoH discards the parent list in _build_offspring.  This is
        an instance-scoped wrapper of the generation call, restored in finally.
        The supported adapter has one sampler; review this boundary on upgrade.
        """
        original = self.evolution.generate_code
        original_generate = self.evolution._generate
        last_call = {}

        def observe_generate(population, operation):
            parents, code, algorithm = original_generate(population, operation)
            last_call.clear()
            last_call.update(parents=parents, code=code)
            return parents, code, algorithm

        def observe(population, operation):
            parents, code, algorithm = original(population, operation)
            # Upstream's duplicate retry discards the retry's parent object.
            # Only the final _generate call can bind parents to final code.
            if code != last_call.get("code"):
                context["generation_parents"] = []
                context["lineage_status"] = "unknown"
            else:
                selected = last_call.get("parents")
                members = [selected] if isinstance(selected, dict) else selected if isinstance(selected, list) else []
                context["generation_parents"] = [
                    {
                        "selected_parent_position": index,
                        "population_member_indices": [position for position, member in enumerate(population)
                                                     if isinstance(member, dict) and member.get("code") == item["code"]],
                        "code_sha256": hashlib.sha256(item["code"].encode("utf-8")).hexdigest(),
                        "algorithm": str(item.get("algorithm") or ""),
                    }
                    for index, item in enumerate(members)
                    if isinstance(item, dict) and isinstance(item.get("code"), str)
                ]
                context["lineage_status"] = ("no_parent" if selected is None and operation == "i1" else
                    "verified" if members and len(context["generation_parents"]) == len(members) else "unknown")
            self.problem.set_evaluation_context(context)
            return parents, code, algorithm

        self.evolution._generate = observe_generate
        self.evolution.generate_code = observe
        try:
            return super()._build_offspring(population_snapshot, operator)
        finally:
            self.evolution.generate_code = original
            self.evolution._generate = original_generate


class ProvenanceEOH(SeedAwareEOH):
    """Official EoH with explicit parent-boundary identity for generated code."""

    def __init__(self, config: Any, problem: Any) -> None:
        super().__init__(config, problem)
        self._provenance_lock = threading.Lock()
        self._candidate_sequence = 0

    def _next_candidate_id(self) -> str:
        with self._provenance_lock:
            self._candidate_sequence += 1
            return f"candidate_{self._candidate_sequence}"

    def _build_offspring(self, population_snapshot, operator):
        candidate_id = self._next_candidate_id()
        context = {
            "origin": "generated",
            "candidate_id": candidate_id,
            "revision": "original",
            "evaluation_id": uuid.uuid4().hex,
            "operator": operator,
        }
        setter = getattr(self.problem, "set_evaluation_context", None)
        if callable(setter):
            setter(context)
        try:
            # SeedAwareEOH does not override this method; this is the pinned
            # official EOH implementation and remains the search authority.
            offspring = self._build_with_parent_evidence(population_snapshot, operator, context)
        finally:
            if callable(setter):
                setter(None)
        if isinstance(offspring, dict):
            offspring.update(
                candidate_id=candidate_id,
                revision="original",
                evaluation_id=context["evaluation_id"],
            )
        return offspring
