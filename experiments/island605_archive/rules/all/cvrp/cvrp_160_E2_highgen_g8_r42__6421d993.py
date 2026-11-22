def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    dists_current = distance_matrix[current_node][unvisited_nodes]
    dists_depot = distance_matrix[depot][unvisited_nodes]

    # Compute regret score: prefer customers closer to current but far from depot
    # to avoid high future detour costs
    regret_scores = dists_depot - dists_current

    # Add small tie-breaker based on index to keep deterministic
    tie_breaker = np.arange(len(unvisited_nodes)) * 1e-10
    scores = regret_scores + tie_breaker

    best_idx = np.argmax(scores)
    return unvisited_nodes[best_idx]
