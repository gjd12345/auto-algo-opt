# 2-opt with infeasible edges excluded

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Apply 2-opt with infeasible edges excluded as introduced in A Method for Solving Traveling-Salesman Problems (1958).
- Some edges cannot be used.
- Abstract-supported identity only; do not copy publisher PDF.

Why selected: DOI-seeded canonical paper for tsp_forbidden.

## 适用条件、假设与限制

Subproblem: Forbidden edges — Some edges cannot be used.

DOI-directed fill. Adapter is not the original algorithm unless the abstract already matches the entrypoint.

## 来源及支持的具体结论

A Method for Solving Traveling-Salesman Problems (1958). DOI 10.1287/opre.6.6.791. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: tsp_construct
- adapter_kind: move_selector
- mappable: possible
- not_the_original: DOI-directed fill. Adapter is not the original algorithm unless the abstract already matches the entrypoint.

```python
def select_2opt_move(tour: np.ndarray, distance_matrix: np.ndarray,
                     move_start: np.ndarray, move_end: np.ndarray,
                     move_delta: np.ndarray, remaining_moves: int) -> int:
    """TSP 2-opt move selector. Candidates are already improving 2-opt moves.

    Return an index into move_start/move_end/move_delta. This is not Lin-Kernighan
    variable-depth search and not Or-opt/3-opt unless those moves are in the list.
    """
    # mechanism: pick among improving 2-opt deltas
    return int(np.argmin(move_delta))
```

Plan 只把机制写入 `operations[].mechanism`，不要把这段代码粘进 plan.json。
