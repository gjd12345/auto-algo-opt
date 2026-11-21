def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    # Scale-normalized savings-style score: prefer nodes close to current
    # and far from depot, expressed as a ratio to avoid absolute-length scale.
    eps = 1e-12
    score = d_cur / (d_dep + eps)

    best_idx = int(np.argmin(score))
    best_score = score[best_idx]

    # Near-tie gate: relative to the best score's magnitude (scale-invariant).
    span = float(score.max() - score.min())
    if span < eps:
        gate = eps
    else:
        gate = 0.05 * span  # relative fraction of the observed spread

    candidates = np.where(score <= best_score + gate)[0]
    if candidates.size == 1:
        return int(unvisited_nodes[best_idx])

    # Secondary stage: among near-ties, prefer larger demand (better packing).
    cand_demands = demands[unvisited_nodes[candidates]]
    best_cand = candidates[int(np.argmax(cand_demands))]
    return int(unvisited_nodes[best_cand])