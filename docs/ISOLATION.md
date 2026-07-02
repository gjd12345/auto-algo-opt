# Go/Python Isolation Contract

## Architecture

```
                Python side (experiment controller)
        eoh_rag/ TOCC / RAG / batch_runner
                     |
                     | CLI + JSON contract
                     v
              bin/agent-go-solver (or Go binary)
                     |
                     v
              Go solver side (dispatch / routing / simulation)
```

## Boundary Rules

### Go side MUST NOT:
- Read Python experiment directories (eoh_rag_workspace/, reports/, rag/)
- Know about RAG cards, TOCC proposals, LLM endpoints
- Import Python modules or call Python scripts
- Contain experiment-specific logic (generations, arms, repeats)

### Python side MUST NOT:
- Depend on Go internal struct fields (Assign.StaIndexesLen, Route[0].CurTime)
- Directly modify go_solver/main.go or go_solver/routing.go
- Assume Go binary location — always use solver_adapter

### Communication contract: CLI + JSON

**Input:**
```json
{
  "instance_id": "rc101_d25_seed1",
  "load_cap": 100,
  "vehicle_num": 25,
  "batches": [...],
  "solver_params": {"memory_size": 16, "sa_steps": 32, "seed": 42}
}
```

**Output:**
```json
{
  "ok": true,
  "objective": 1234.56,
  "res": 0.82,
  "j": 0.91,
  "runtime_ms": 182,
  "vehicle_count": 12,
  "error": null
}
```

## Solver Access

The Go solver (`go_solver/main.go`, `go_solver/routing.go`) is self-contained and exposes no Python dependencies.
Python accesses the Go solver through `eoh_rag/solver_adapter/go_solver.py`.
The EOH experiment runner (`eoh_single_runner.py`) uses official EoH's Python wrapper
rather than the Go solver directly — they solve different problem types.

## Extension Points

The isolation contract keeps the following open:

- The Go solver can be wrapped in `cmd/solver/main.go` behind stable CLI flags.
- All Python–Go interaction goes through `solver_adapter.run_go_solver()`.
- Because the boundary is CLI + JSON only, the Go solver can run as a separate binary or submodule without changing the Python side.
