def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        # Seed route: farthest from depot
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]
    else:
        # Nearest neighbor within route
        nearest_idx = np.argmin(distance_matrix[current_node][unvisited_nodes])
        nearest_node = unvisited_nodes[nearest_idx]
        nearest_dist = distance_matrix[current_node][nearest_node]

        # Voluntary return if nearest is farther than distance to depot and capacity is not nearly full
        dist_to_depot = distance_matrix[current_node][depot]
        total_demand_visited = demands[current_node]  # not exact, but heuristic
        # Heuristic: return if nearest is too far and we have capacity to spare (e.g., > 20% remaining)
        if nearest_dist > dist_to_depot and rest_capacity > 0.2 * (demands[unvisited_nodes].max() if len(unvisited_nodes) > 0 else 1):
            return depot
        return nearest_node
