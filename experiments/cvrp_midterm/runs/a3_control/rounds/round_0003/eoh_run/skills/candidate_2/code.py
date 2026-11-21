def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction.

    Args:
        current_node:    index of the current node (0 = depot)
        depot:           index of the depot (always 0)
        unvisited_nodes: array of feasible unvisited customer indices
                         (already filtered to satisfy remaining capacity)
        rest_capacity:   remaining vehicle capacity
        demands:         demand of every node (index 0 = depot demand = 0)
        distance_matrix: pairwise Euclidean distance matrix
    Returns:
        Index of the next node to visit, or 0 to return to the depot early.
    """
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_depot = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]
    cap = rest_capacity if rest_capacity > 1e-9 else 1.0

    n = unvisited_nodes.size
    best_score = None
    best_idx = 0

    for i in range(n):
        node_i = unvisited_nodes[i]
        # Best follow-up from candidate i to any other unvisited node
        if n > 1:
            sub = np.delete(np.arange(n), i)
            next_nodes = unvisited_nodes[sub]
            d_next = distance_matrix[node_i][next_nodes]
            follow_cost = float(np.min(d_next))
        else:
            follow_cost = 0.0

        # Regret: how much worse to go via depot than via a follow-up trip
        depot_cost = d_depot[i] + float(distance_matrix[depot][node_i])
        # Extra distance if we serve this node now instead of a direct return
        detour = d_cur[i] + follow_cost - d_depot[i]
        if detour < 0:
            detour = 0.0

        fill = dem[i] / cap  # 0..1, fill ratio

        # Combined priority: prefer high fill and small detour, penalize
        # nodes that are far from depot (leaving them stranded is costly).
        urgency = 1.0 / (1.0 + depot_cost)
        score = (fill + 0.5) * urgency - 0.3 * detour / (1.0 + d_cur[i] + d_depot[i])

        if best_score is None or score > best_score:
            best_score = score
            best_idx = int(node_i)

    return best_idx