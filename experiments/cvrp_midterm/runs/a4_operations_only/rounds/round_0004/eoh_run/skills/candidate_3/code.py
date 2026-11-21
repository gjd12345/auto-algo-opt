def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    cur = distance_matrix[current_node][unvisited_nodes]
    d_depot = distance_matrix[depot][unvisited_nodes]
    d_cur_depot = distance_matrix[current_node][depot]

    # Savings relative to returning to depot from current node
    savings = d_cur_depot - cur - d_depot
    max_sav = float(np.max(np.abs(savings))) if savings.size > 0 else 1.0
    if max_sav <= 0:
        max_sav = 1.0

    # Primary score: nearest distance minus normalized savings bonus
    scores = cur - (savings / max_sav)

    order = np.argsort(scores)
    best_score = scores[order[0]]
    tol = 1e-9 + 1e-6 * (abs(best_score) + 1.0)
    tied = order[scores[order] <= best_score + tol]

    if tied.size == 1:
        return int(unvisited_nodes[tied[0]])

    tie_nodes = unvisited_nodes[tied]
    cap = max(rest_capacity, 1e-9)
    fill = demands[tie_nodes] / cap
    best_fill = float(np.max(fill))
    candidates = tie_nodes[fill >= best_fill - 1e-12]

    cand_dists = distance_matrix[current_node][candidates]
    return int(candidates[np.argmin(cand_dists)])