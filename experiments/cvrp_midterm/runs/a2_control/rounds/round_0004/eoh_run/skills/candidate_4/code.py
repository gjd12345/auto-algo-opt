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
    idx = np.asarray(unvisited_nodes, dtype=int)
    d_cur = distance_matrix[current_node][idx]
    d_dep = distance_matrix[depot][idx]
    dem = demands[idx].astype(float)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0

    fill = np.clip(dem / cap, 0.0, 1.0)

    # Detour cost of inserting this node before returning to depot:
    # going current -> node -> depot vs current -> depot.
    detour = d_cur + d_dep - distance_matrix[current_node][depot]

    # Concave fill reward: sqrt amplifies the value of nearly-full loads
    # without over-rewarding tiny demands.
    fill_reward = np.sqrt(fill + 1e-9)

    # Demand-adjusted detour ratio: pay detour per unit of fill benefit.
    ratio = detour / (fill_reward + 1e-6)

    # Mild tie-break toward the farther depot leg to avoid premature returns.
    score = ratio - 0.05 * d_dep

    return int(idx[np.argmin(score)])