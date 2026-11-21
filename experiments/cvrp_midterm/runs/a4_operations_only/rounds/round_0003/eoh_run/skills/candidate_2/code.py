def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    cur_to = distance_matrix[current_node][unvisited_nodes]
    dep_to = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    cap = max(rest_capacity, 1e-9)
    mean_dep = float(np.mean(dep_to)) if dep_to.size > 0 else 1.0
    if mean_dep <= 0:
        mean_dep = 1.0
    mean_cur = float(np.mean(cur_to)) if cur_to.size > 0 else 1.0
    if mean_cur <= 0:
        mean_cur = 1.0

    # Regret-style: savings from not needing a separate depot trip,
    # plus a capacity-utilization bonus, minus immediate travel cost.
    utilization = dem / cap
    savings = dep_to / mean_dep
    immediate = cur_to / mean_cur
    scores = 1.2 * savings + 1.0 * utilization - 0.6 * immediate

    order = np.argsort(-scores)
    best = scores[order[0]]
    tol = 1e-9 + 1e-6 * (abs(best) + 1.0)
    tied = order[scores[order] >= best - tol]

    if tied.size == 1:
        return int(unvisited_nodes[tied[0]])

    # Secondary: prefer the candidate whose return trip to depot is cheapest
    # relative to its demand, so routes fill up while staying cheap to close.
    tie_nodes = unvisited_nodes[tied]
    tie_dep = distance_matrix[depot][tie_nodes]
    tie_dem = demands[tie_nodes]
    tie_cap = max(rest_capacity, 1e-9)
    closeness = tie_dep * (1.0 + tie_dem / tie_cap)
    return int(tie_nodes[np.argmin(closeness)])