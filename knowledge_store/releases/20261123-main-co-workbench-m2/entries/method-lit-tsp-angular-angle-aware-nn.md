# Angle-aware NN

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Apply Angle-aware NN as introduced in A Sharper Explicit Bound on the Subtour-LP Integrality Gap for Metric TSP (2026).
- Cost uses turning angles.
- Abstract-supported identity only; do not copy publisher PDF.

Why selected: DOI-seeded canonical paper for tsp_angular.

## 适用条件、假设与限制

Subproblem: Angular-metric TSP — Cost uses turning angles.

DOI-directed fill. Adapter is not the original algorithm unless the abstract already matches the entrypoint.

## 来源及支持的具体结论

A Sharper Explicit Bound on the Subtour-LP Integrality Gap for Metric TSP (2026). DOI 10.2139/ssrn.7378178. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: tsp_construct
- adapter_kind: next_node_score
- mappable: possible
- not_the_original: DOI-directed fill. Adapter is not the original algorithm unless the abstract already matches the entrypoint.

```python
def select_next_node(current_node: int, start_node: int, unvisited_nodes: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """TSP construct adapter. Evaluator already truncated the candidate list.

    Replace the score using the screened heuristic steps. Returning a city
    that is not in unvisited_nodes is invalid_return. This is not insertion
    into a partial tour and not 2-opt.
    """
    # mechanism: score each unvisited city; pick the best legal index
    return unvisited_nodes[int(np.argmin(distance_matrix[current_node][unvisited_nodes]))]
```

Plan 只把机制写入 `operations[].mechanism`，不要把这段代码粘进 plan.json。
