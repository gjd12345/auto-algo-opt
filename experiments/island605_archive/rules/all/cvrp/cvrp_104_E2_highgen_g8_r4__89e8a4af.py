def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Start a new route: pick the customer maximizing savings = dist(depot, u) - nearest distance to any visited node proxy
        depot_distances = distance_matrix[depot][unvisited_nodes]
        # Use farthest as a simple proxy for savings to seed routes outward
        return unvisited_nodes[np.argmax(depot_distances)]
    else:
        # En route: use a savings-like rule: prefer customers with high (dist(depot,u) - dist(current,u))
        depot_dists = distance_matrix[depot][unvisited_nodes]
        current_dists = distance_matrix[current_node][unvisited_nodes]
        savings = depot_dists - current_dists
        best_idx = np.argmax(savings)
        candidate = unvisited_nodes[best_idx]
        # Return to depot if going directly to depot is shorter than going to candidate and then later returning
        if distance_matrix[current_node][depot] < distance_matrix[current_node][candidate]:
            return depot
        return candidate
