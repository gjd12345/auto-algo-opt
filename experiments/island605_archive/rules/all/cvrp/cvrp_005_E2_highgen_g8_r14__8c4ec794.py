def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    if current_node == depot:
        # Seed route with farthest feasible customer
        distances_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(distances_from_depot)]
    else:
        # Compute savings: distance from depot to customer minus distance from current to customer
        depot_distances = distance_matrix[depot][unvisited_nodes]
        current_distances = distance_matrix[current_node][unvisited_nodes]
        savings = depot_distances - current_distances
        # If remaining capacity is very small, prioritize nearest neighbor for local completion
        if rest_capacity < 10:
            return unvisited_nodes[np.argmin(current_distances)]
        # Otherwise, select customer with maximum savings (regret-like), break ties by nearest distance
        max_saving = np.max(savings)
        candidates = unvisited_nodes[savings == max_saving]
        if len(candidates) == 1:
            return candidates[0]
        # Tie-break: pick nearest among candidates
        cand_distances = distance_matrix[current_node][candidates]
        return candidates[np.argmin(cand_distances)]
