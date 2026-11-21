def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    # Primary score: current distance + squared depot distance term (replaces the depot term)
    score = d_cur + (d_dep * d_dep) / (rest_capacity + 1.0)
    order = np.argsort(score)
    best_idx = order[0]
    best_score = score[best_idx]
    # Secondary ordering stage: among near-ties, prefer the node farthest from depot
    # (to leave closer nodes for later, cheap return)
    tie_mask = np.abs(score - best_score) <= 1e-9 + 0.05 * abs(best_score)
    candidates = unvisited_nodes[tie_mask]
    if candidates.size > 1:
        cand_dep = distance_matrix[depot][candidates]
        return int(candidates[np.argmax(cand_dep)])
    return int(unvisited_nodes[best_idx])