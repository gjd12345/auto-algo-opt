"""Official EOH smoke entry point.

Re-exports the problem registry (:mod:`eoh_rag.experiments.problem_registry`),
which defines the supported optimization problems and drives a lightweight
end-to-end smoke run over them. Import from here or from ``problem_registry``
interchangeably.
"""
from eoh_rag.experiments.problem_registry import *  # noqa: F401,F403
