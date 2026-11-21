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

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
    dem = demands[unvisited_nodes].astype(float)

    cap = max(rest_capacity, 1e-9)

    # Clarke-Wright style savings: benefit of linking current -> candidate
    # instead of returning to depot from both ends.
    savings = d_cur * 0.0 + (d_cur + d_dep - d_cur)  # placeholder replaced below
    savings = distance_matrix[depot][current_node] + d_dep - d_cur

    # Capacity fill: prefer demands that pack the vehicle tightly.
    fill = dem / cap

    # Combine: maximize savings, and reward tight remaining-fit.
    scores = -savings / (1.0 + d_cur) - 0.6 * fill + 0.15 * (d_cur / (1.0 + d_dep))

    return int(unvisited_nodes[np.argmin(scores)])