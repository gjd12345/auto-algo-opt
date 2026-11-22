def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Start route: go to the farthest customer to seed distant clusters
        depot_distances = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(depot_distances)]
    else:
        # Nearest neighbor with a threshold: return to depot if the nearest customer
        # is not significantly closer than returning to the depot
        nearest_customer_idx = np.argmin(distance_matrix[current_node][unvisited_nodes])
        nearest_customer = unvisited_nodes[nearest_customer_idx]
        nearest_dist = distance_matrix[current_node][nearest_customer]
        depot_dist = distance_matrix[current_node][depot]
        # Return to depot if nearest customer is less than 20% closer than the depot distance
        if nearest_dist * 1.25 >= depot_dist:
            return depot
        return nearest_customer
