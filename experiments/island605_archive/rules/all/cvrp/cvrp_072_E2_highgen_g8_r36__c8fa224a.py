def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        distances_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(distances_from_depot)]
    else:
        current_dist = distance_matrix[current_node][unvisited_nodes]
        depot_dist = distance_matrix[depot][unvisited_nodes]
        regret = current_dist - 0.5 * depot_dist  # penalty if far from depot relative to current
        demand_penalty = demands[unvisited_nodes] / rest_capacity
        score = regret * (1.0 + demand_penalty)
        best_idx = np.argmin(score)
        # Return to depot if the best candidate is farther than twice the average unvisited distance from depot
        if current_dist[best_idx] > 2.0 * np.mean(depot_dist):
            return depot
        return unvisited_nodes[best_idx]
