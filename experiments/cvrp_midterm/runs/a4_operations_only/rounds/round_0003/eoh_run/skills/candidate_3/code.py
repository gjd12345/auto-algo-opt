def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    cur_to = distance_matrix[current_node][unvisited_nodes]
    dep_to = distance_matrix[depot][unvisited_nodes]
    root_dep = distance_matrix[depot][current_node]
    dem = demands[unvisited_nodes]

    cap = max(rest_capacity, 1e-9)
    mean_dep = float(np.mean(dep_to)) if dep_to.size > 0 else 1.0
    if mean_dep <= 0:
        mean_dep = 1.0
    mean_cur = float(np.mean(cur_to)) if cur_to.size > 0 else 1.0
    if mean_cur <= 0:
        mean_cur = 1.0

    # Detour term: extra distance incurred by inserting the customer now
    # instead of returning straight to the depot from the current node.
    detour = cur_to + dep_to - root_dep
    mean_detour = float(np.mean(detour)) if detour.size > 0 else 1.0
    if mean_detour <= 0:
        mean_detour = 1.0

    savings = dep_to / mean_dep
    immediate = cur_to / mean_cur
    detour_norm = detour / mean_detour

    scores = 1.2 * savings - 0.6 * immediate - 1.0 * detour_norm

    order = np.argsort(-scores)
    best = scores[order[0]]
    tol = 1e-9 + 1e-6 * (abs(best) + 1.0)
    tied = order[scores[order] >= best - tol]

    if tied.size == 1:
        return int(unvisited_nodes[tied[0]])

    # Secondary: among near-ties, prefer high demand per unit detour
    # (density), breaking remaining ties by the cheapest depot return.
    tie_nodes = unvisited_nodes[tied]
    tie_detour = (distance_matrix[current_node][tie_nodes]
                  + distance_matrix[depot][tie_nodes]
                  - root_dep)
    tie_detour = np.maximum(tie_detour, 1e-9)
    tie_dem = demands[tie_nodes]
    density = tie_dem / tie_detour
    tie_dep = distance_matrix[depot][tie_nodes]
    key = -density + 1e-6 * tie_dep
    return int(tie_nodes[np.argmin(key)])