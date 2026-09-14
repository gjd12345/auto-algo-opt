"""Offline, versioned optimisation knowledge-base tooling.

The package is deliberately independent from agent_skill_loop. It
reads Git objects and local workspace files only; it never imports the
production Session runtime and never makes model or solver requests.
"""

__version__ = "0.1.1"
SCHEMA_VERSION = "knowledge-v1"
CLASSIFICATION_VERSION = "taxonomy-v2"

__all__ = ["__version__", "SCHEMA_VERSION", "CLASSIFICATION_VERSION"]
