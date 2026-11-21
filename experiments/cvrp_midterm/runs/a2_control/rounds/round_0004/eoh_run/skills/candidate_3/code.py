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
    # Relative position: how much closer to depot vs current node
    closeness = d_cur / (d_cur + d_dep + 1e-9)

    score = d_cur * (1.0 + 0.8 * closeness) - 0.9 * d_dep * fill + 1.4 * d_cur * (1.0 - fill)

    return int(idx[np.argmin(score)])