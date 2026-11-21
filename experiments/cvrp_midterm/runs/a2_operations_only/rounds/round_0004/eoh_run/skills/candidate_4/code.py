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
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    savings = d_dep - d_cur

    cap_denom = rest_capacity if rest_capacity > 1e-9 else 1e-9
    fill = demands[unvisited_nodes] / cap_denom

    # multiplicative ratio: savings relative to demand pressure
    # small-demand customers only win when their savings is proportionally large
    ratio = savings / np.maximum(fill, 1e-6)

    best = np.max(ratio)
    tol = 1e-6 * (abs(best) + 1.0)
    near = np.where(ratio >= best - tol)[0]
    if near.size > 1:
        return unvisited_nodes[near[np.argmin(d_cur[near])]]
    return unvisited_nodes[np.argmax(ratio)]