def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot
    cur = distance_matrix[current_node][unvisited_nodes]
    cap = max(rest_capacity, 1e-9)
    fill = demands[unvisited_nodes] / cap  # fraction of remaining capacity used
    # Primary: nearest neighbor, weakly rewarded for high fill ratio
    scores = cur - 1.0 * fill
    order = np.argsort(scores)
    best_score = scores[order[0]]
    tol = 1e-9 + 1e-6 * (abs(best_score) + 1.0)
    tied = order[scores[order] <= best_score + tol]
    if tied.size == 1:
        return int(unvisited_nodes[tied[0]])
    # Secondary: prefer larger demand (fuller loads) among near ties
    tie_nodes = unvisited_nodes[tied]
    d = demands[tie_nodes]
    best_d_idx = int(np.argmax(d))
    candidates = tie_nodes[d >= d[best_d_idx] - 1e-12]
    # Final tie-break: shorter distance to current node
    dists = distance_matrix[current_node][candidates]
    return int(candidates[np.argmin(dists)])