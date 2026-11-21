def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    eps = 1e-9
    score = d_dep / (d_cur + eps)

    s_min = np.min(score)
    s_max = np.max(score)
    span = s_max - s_min
    # Scale-invariant relative gate: tolerance proportional to |score| magnitude.
    tol = 0.15 * (abs(s_max) + eps)
    if span > 0 and tol > span:
        tol = span
    near = score >= (s_max - tol)
    candidates = unvisited_nodes[near]
    if candidates.size == 0:
        candidates = unvisited_nodes

    cand_demands = demands[candidates]
    cand_dep = distance_matrix[depot][candidates]
    capacity_factor = rest_capacity - cand_demands
    secondary = cand_dep / (capacity_factor + 1.0)
    best_idx = int(np.argmax(secondary))
    return int(candidates[best_idx])