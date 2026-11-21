def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    eps = 1e-9
    cap_frac = dem / (rest_capacity + eps)
    score = cap_frac / (d_cur + eps) + 1.0 / (d_dep + eps)

    s_min = np.min(score)
    s_max = np.max(score)
    span = s_max - s_min
    if span <= eps:
        return int(unvisited_nodes[np.argmin(d_cur)])
    tie_tol = 0.05 * span
    near = score >= (s_max - tie_tol)
    candidates = unvisited_nodes[near]
    if candidates.size == 0:
        candidates = unvisited_nodes
    best_idx = np.argmin(distance_matrix[current_node][candidates])
    return int(candidates[best_idx])