"""Go solver adapter — stable Python interface to the Go dispatch solver.

All Python code that needs to call the Go solver should use this module.
Never directly invoke `go run main.go` or parse Go internal outputs.

The Go solver is a separate concern (dynamic dispatch/routing) from the
EOH experiment runner (heuristic evolution for TSP/CVRP/BP). They solve
different problem types and should not be confused.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_SOLVER_BINARY = "bin/agent-go-solver"


def run_go_solver(
    input_path: str | Path,
    output_path: str | Path,
    *,
    solver_binary: str = "",
    timeout_s: int = 120,
    multi: int = 1,
) -> dict[str, Any]:
    """Run the Go dispatch solver on an input instance.

    Parameters
    ----------
    input_path : path to input JSON (batches + params)
    output_path : path where result JSON will be written
    solver_binary : path to compiled solver binary (default: bin/agent-go-solver)
    timeout_s : max execution time
    multi : vehicle multiplier argument

    Returns
    -------
    dict with keys: ok, objective, runtime_ms, error, etc.
    """
    binary = solver_binary or DEFAULT_SOLVER_BINARY
    if not Path(binary).exists():
        # Fallback: try go run
        cmd = ["go", "run", ".", str(input_path), str(multi)]
    else:
        cmd = [str(binary), str(input_path), str(multi)]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        if proc.returncode != 0:
            return {
                "ok": False,
                "error": f"solver exit code {proc.returncode}: {proc.stderr[:200]}",
                "objective": None,
                "runtime_ms": None,
            }

        # Parse output (current format: solver prints JSON to stdout)
        # Future: solver writes to output_path directly
        try:
            result = json.loads(proc.stdout)
            result["ok"] = True
            return result
        except json.JSONDecodeError:
            return {
                "ok": False,
                "error": "solver stdout is not valid JSON (legacy format)",
                "raw_stdout": proc.stdout[:500],
                "objective": None,
                "runtime_ms": None,
            }

    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": f"solver timeout after {timeout_s}s",
            "objective": None,
            "runtime_ms": None,
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "error": f"solver binary not found: {binary}",
            "objective": None,
            "runtime_ms": None,
        }
