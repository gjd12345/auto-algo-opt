# Online feasible NN

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Apply Online feasible NN as introduced in Stochastic dynamic vehicle routing problem survey (2024).
- Requests arrive online.
- Abstract-supported identity only; do not copy publisher PDF.

Why selected: DOI-seeded canonical paper for cvrp_dynamic.

## 适用条件、假设与限制

Subproblem: Dynamic VRP — Requests arrive online.

DOI-directed fill. Adapter is not the original algorithm unless the abstract already matches the entrypoint.

## 来源及支持的具体结论

Stochastic dynamic vehicle routing problem survey (2024). DOI 10.47344/sdubnts.v62i1.959. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: cvrp_construct
- adapter_kind: next_node_score
- mappable: possible
- not_the_original: DOI-directed fill. Adapter is not the original algorithm unless the abstract already matches the entrypoint.

```python
def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """CVRP construct adapter. unvisited_nodes are already capacity-feasible.

    Return 0 to go back to the depot early. This is not Clarke-Wright merge
    of n singleton routes, not sweep clustering, and not granular tabu.
    """
    # mechanism: score feasible customers; depot return is allowed
    return unvisited_nodes[int(np.argmin(distance_matrix[current_node][unvisited_nodes]))]
```

Plan 只把机制写入 `operations[].mechanism`，不要把这段代码粘进 plan.json。
