def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot
    
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    
    # Primary score: savings-like term - distance to current minus distance back to depot,
    # normalized by current-node distance to avoid scale sensitivity of absolute lengths.
    # Using ratio d_dep / (d_cur + eps) as "return savings" priority.
    eps = 1e-9
    score = d_dep / (d_cur + eps)
    
    # Secondary: among near-ties in primary score, prefer closer to current node.
    max_score = np.max(score)
    tie_tol = 0.02 * max_score
    near = score >= (max_score - tie_tol)
    candidates = unvisited_nodes[near]
    if candidates.size == 0:
        candidates = unvisited_nodes
    best_idx = np.argmin(distance_matrix[current_node][candidates])
    return int(candidates[best_idx])