def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Start of route: pick the farthest feasible customer
        dists_from_depot = distance_matrix[depot, unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]
    else:
        # En route: nearest neighbor with vanishing depot penalty
        dists = distance_matrix[current_node, unvisited_nodes]
        dists_to_depot = distance_matrix[depot, unvisited_nodes]
        max_demand = np.max(demands[demands > 0]) if np.any(demands > 0) else 1.0
        # Penalty proportional to remaining capacity; zero when rest_capacity is 0
        penalty = (rest_capacity / max_demand) * 0.3 * dists_to_depot
        scores = dists - penalty
        return unvisited_nodes[np.argmin(scores)]
