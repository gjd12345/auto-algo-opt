def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction.

    Args:
        current_node:    index of the current node (0 = depot)
        depot:           index of the depot (always 0)
        unvisited_nodes: array of feasible unvisited customer indices
                         (already filtered to satisfy remaining capacity)
        rest_capacity:   remaining vehicle capacity
        demands:         demand of every node (index 0 = depot demand = 0)
        distance_matrix: pairwise Euclidean distance matrix
    Returns:
        Index of the next node to visit, or 0 to return to the depot early.
    """
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_depot = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    cap = rest_capacity if rest_capacity > 1e-9 else 1.0
    load_ratio = np.clip(dem / cap, 0.0, 1.0)

    # Regret-style saving: benefit of serving this node now rather than
    # detouring from the depot on a future route.
    saving = d_depot + d_cur - distance_matrix[depot][unvisited_nodes] * 0.0
    detour = d_cur + d_depot - 0.0

    # Normalize by a nonlinear function of the load fill to reward fuller loads.
    denom = (detour + 1e-9) * (1.0 + load_ratio) ** 2

    # Prefer nodes with high saving density and heavier relative demand.
    score = -(load_ratio * d_depot + 0.5 * dem) / denom

    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])