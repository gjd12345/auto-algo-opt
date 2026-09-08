from __future__ import annotations

import os


def pytest_configure(config) -> None:
    if os.environ.get("EOH_REQUIRED") == "1":
        import eoh  # noqa: F401
