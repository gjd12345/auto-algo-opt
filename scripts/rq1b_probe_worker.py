"""Sanitized worker for RQ1b CVRP behavior calls."""
from __future__ import annotations
import json
import sys
import contextlib
import hashlib
import numpy as np
from eoh_rag.fme.pilot_evaluation import _SAFE_BUILTINS, _as_index, _validate_candidate_ast, _QuietSink


def main() -> None:
    request = json.loads(sys.stdin.buffer.read().decode())
    code, panel = request.get("code"), request.get("panel")
    if not isinstance(code, str) or not isinstance(panel, dict) or not isinstance(panel.get("states"), list):
        raise ValueError("invalid_request")
    supplied = panel.get("content_hash")
    body = dict(panel); body.pop("content_hash", None)
    expected = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    if supplied != expected: raise ValueError("panel_hash_mismatch")
    tree = _validate_candidate_ast(code, "select_next_node")
    def restricted(name, globals=None, locals=None, fromlist=(), level=0):
        if level or name not in ("numpy", "math"): raise ImportError("restricted_import")
        return np if name == "numpy" else __import__("math")
    builtins = dict(_SAFE_BUILTINS); builtins["__import__"] = restricted
    ns = {"__builtins__": builtins, "np": np, "numpy": np, "math": __import__("math")}
    with contextlib.redirect_stdout(_QuietSink()), contextlib.redirect_stderr(_QuietSink()):
        exec(compile(tree, "<rq1b-candidate>", "exec"), ns, ns)
    fn = ns.get("select_next_node")
    if not callable(fn): raise ValueError("missing_entrypoint")
    choices, rows = {}, []
    for state in panel["states"]:
        sid = state.get("state_id")
        try:
            nodes = np.asarray(state["unvisited_nodes"], dtype=int)
            demands = np.asarray(state["demands"], dtype=float)
            matrix = np.asarray(state["distance_matrix"], dtype=float)
            if nodes.ndim != 1 or nodes.size == 0 or not np.all(np.isfinite(matrix)) or not np.all(np.isfinite(demands)):
                raise ValueError("invalid_state")
            n0, d0, m0 = nodes.copy(), demands.copy(), matrix.copy()
            with contextlib.redirect_stdout(_QuietSink()), contextlib.redirect_stderr(_QuietSink()):
                value = fn(int(state["current_node"]), int(state["depot"]), nodes, float(state["rest_capacity"]), demands, matrix)
            if not np.array_equal(nodes, n0) or not np.array_equal(demands, d0) or not np.array_equal(matrix, m0):
                raise ValueError("candidate_mutated_input")
            choice = _as_index(value, set(int(x) for x in n0) | {int(state["depot"])})
            if choice is None: raise ValueError("invalid_return")
            choices[str(sid)] = choice
            rows.append({"state_id": sid, "valid": True, "choice": choice, "error_code": None})
        except ValueError as exc:
            choices[str(sid)] = None
            rows.append({"state_id": sid, "valid": False, "choice": None, "error_code": str(exc) if str(exc) in {"candidate_mutated_input", "invalid_return", "invalid_state"} else "candidate_error"})
        except Exception:
            choices[str(sid)] = None
            rows.append({"state_id": sid, "valid": False, "choice": None, "error_code": "candidate_exception"})
    print(json.dumps({"valid": all(row["valid"] for row in rows), "choices": choices, "state_results": rows, "panel_hash": supplied, "error_code": None if all(row["valid"] for row in rows) else "partial_state_failure"}, separators=(",", ":")))


if __name__ == "__main__":
    try: main()
    except Exception as exc:
        print(json.dumps({"valid": False, "choices": {}, "state_results": [], "error_code": str(exc) if str(exc) in {"invalid_request", "missing_entrypoint", "forbidden_name", "forbidden_attribute", "forbidden_import", "invalid_code"} else "candidate_error"}, separators=(",", ":")))
