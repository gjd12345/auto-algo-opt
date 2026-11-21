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
    load_ratio = dem / cap

    n = unvisited_nodes.size
    # Rank-based aggregation: lower distance is better (rank 0 = best)
    rank_cur = np.argsort(np.argsort(d_cur)).astype(np.float64)
    rank_dep = np.argsort(np.argsort(d_depot)).astype(np.float64)
    # Higher load ratio is better -> invert ranking
    rank_load = np.argsort(np.argsort(-load_ratio)).astype(np.float64)

    denom = float(n) if n > 1 else 1.0
    score = (0.55 * rank_cur + 0.30 * rank_dep + 0.15 * rank_load) / denom

    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])