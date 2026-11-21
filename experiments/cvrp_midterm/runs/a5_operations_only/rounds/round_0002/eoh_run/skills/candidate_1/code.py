def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    # Savings-style score: larger savings (depot round trip avoided) is better.
    savings = 2.0 * d_dep - d_cur
    best = np.max(savings)
    # Secondary ordering: among near-tied top candidates, pick nearest to current.
    tol = 1e-9 * (1.0 + abs(best))
    mask = savings >= best - tol
    candidates = unvisited_nodes[mask]
    if candidates.size == 1:
        return int(candidates[0])
    cand_d_cur = distance_matrix[current_node][candidates]
    return int(candidates[np.argmin(cand_d_cur)])