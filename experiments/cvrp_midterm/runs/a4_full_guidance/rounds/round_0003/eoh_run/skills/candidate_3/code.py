def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    eps = 1e-9
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    # Scale-free normalized savings: how much closer to the depot than to
    # the current node a candidate sits, expressed as a ratio in (-1, 1].
    score = (d_dep - d_cur) / (d_dep + d_cur + eps)

    s_max = np.max(score)
    s_min = np.min(score)
    span = s_max - s_min
    tol = 0.05 * span
    near = score >= (s_max - tol)
    candidates = unvisited_nodes[near]
    if candidates.size == 0:
        candidates = unvisited_nodes

    cand_cur = distance_matrix[current_node][candidates]
    best = candidates[int(np.argmin(cand_cur))]
    return int(best)