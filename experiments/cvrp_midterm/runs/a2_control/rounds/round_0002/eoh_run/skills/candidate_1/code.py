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
    # Distances from current node and from depot to candidates
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    # Demands of candidates
    q = demands[unvisited_nodes]

    # Residual capacity after serving each candidate
    residual = rest_capacity - q
    # Penalise leaving very little capacity: higher when residual is small
    # Normalise by rest_capacity (guard against zero)
    cap = rest_capacity if rest_capacity > 0 else 1.0
    fill_penalty = (q / cap) ** 2  # prefer filling capacity smoothly

    # Savings-style score: prefer nearby customers but be wary of long return trips
    # Lower score = better
    score = d_cur + 0.35 * d_dep + 0.5 * fill_penalty * (d_cur + d_dep) \
            - 0.15 * residual / cap * d_dep

    return int(unvisited_nodes[np.argmin(score)])