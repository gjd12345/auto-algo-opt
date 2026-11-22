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
    if len(unvisited_nodes) == 0:
        return depot

    eps = 1e-10
    dist_to_current = distance_matrix[current_node][unvisited_nodes] + eps
    dist_from_depot = distance_matrix[depot][unvisited_nodes]

    # Regret: count how many other feasible nodes each unvisited node can be inserted after (excluding itself)
    n = len(unvisited_nodes)
    regret_scores = np.zeros(n)
    for i, u in enumerate(unvisited_nodes):
        count = 0
        for v in unvisited_nodes:
            if v != u and demands[u] + demands[v] <= rest_capacity:
                count += 1
        regret_scores[i] = count + 1  # +1 to avoid zero

    # Capacity-aware blending
    max_demand = demands.max() if demands.max() > 0 else 1.0
    capacity_ratio = rest_capacity / max_demand
    weight_far = min(1.0, capacity_ratio)

    # Score: higher regret (fewer options) is prioritized; blended with distance terms
    scores = (1.0 / regret_scores) + weight_far * (dist_from_depot / dist_to_current) + (1 - weight_far) * (1.0 / dist_to_current)

    best_idx = unvisited_nodes[np.argmax(scores)]
    return best_idx
