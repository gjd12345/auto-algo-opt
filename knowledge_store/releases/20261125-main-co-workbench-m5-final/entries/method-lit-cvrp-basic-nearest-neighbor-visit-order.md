# Nearest Neighbor visit order

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Among remaining customers, choose the nearest one as the next visit

Why selected: Abstract states Nearest Neighbor is used to order visits, which is next-customer scoring by proximity.

## 适用条件、假设与限制

Subproblem: Capacitated VRP — One depot, capacity, visit each customer once.

Application paper: Clarke-Wright forms routes, then NN orders visits. Evaluator already filters capacity; this adapter is only the NN choice, not CW merge and not Sweep.

## 来源及支持的具体结论

Penerapan Algoritma Clarke and Wright Saving dalam Capacitated Vehicle Routing Problem dengan Optimasi Nearest Neighbor untuk Rute Terpendek (2026). DOI 10.26760/mindjournal.v11i1.1-14. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: cvrp_construct
- adapter_kind: next_node_score
- mappable: possible
- not_the_original: Application paper: Clarke-Wright forms routes, then NN orders visits. Evaluator already filters capacity; this adapter is only the NN choice, not CW merge and not Sweep.

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
