"""Public entry point for the Trace-Conditioned Operator-Card Controller.

Exposes the controller API from :mod:`eoh_rag.tocc.controller` so that
AGENTS.md / SKILL.md references and experiment scripts can import it from a
single stable path. The controller reads an ``official_eoh_run_summary.json``
trace and produces a diagnosis plus a recommended operator-card set and query.
It does not call an LLM and does not modify files.
"""
from eoh_rag.tocc.controller import *  # noqa: F401,F403
from eoh_rag.tocc.controller import TOCCDecision, diagnose  # noqa: F401
