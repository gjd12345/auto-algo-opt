def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        distances_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(distances_from_depot)]

    current_distances = distance_matrix[current_node][unvisited_nodes]
    depot_distances = distance_matrix[depot][unvisited_nodes]
    regret = depot_distances - current_distances

    if np.max(regret) > 0:
        candidates = unvisited_nodes[regret > 0]
        if len(candidates) > 0:
            candidate_regrets = regret[regret > 0]
            candidate_demands = demands[candidates]
            # Tie-break by higher demand
            candidate_scores = candidate_regrets + 0.1 * (candidate_demands / rest_capacity)
            return candidates[np.argmax(candidate_scores)]

    return unvisited_nodes[np.argmin(current_distances)]
