"""Parent-side provenance adapters for the pinned official EoH engine.

The official evaluator runs in a fresh spawned process.  Provenance therefore
cannot be inferred from mutable counters stored on ``FrozenProblem``: every
child receives its own copy of those counters.  These small adapters bind
identity before the official call and clear seed bindings after seed
initialisation, while leaving EoH selection, operators, and population
management untouched.
"""

from __future__ import annotations

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
            offspring = super()._build_offspring(population_snapshot, operator)
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
