def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    # If no feasible customers remain, return to depot
    if len(unvisited_nodes) == 0:
        return depot

    # If we are at the depot (starting a new route), use far-first seeding
    if current_node == depot:
        # Prefer distant customers to seed routes toward far clusters
        distances_from_depot = distance_matrix[depot][unvisited_nodes]
        far_node = unvisited_nodes[np.argmax(distances_from_depot)]
        return far_node

    # Otherwise, use nearest-neighbor selection
    current_distances = distance_matrix[current_node][unvisited_nodes]
    nearest_idx = np.argmin(current_distances)
    nearest_customer = unvisited_nodes[nearest_idx]
    dist_to_nearest = current_distances[nearest_idx]

    # Check if returning to depot is better than going to the nearest customer
    dist_to_depot = distance_matrix[current_node][depot]
    # If returning to depot is shorter than the next customer distance, close route
    if dist_to_depot < dist_to_nearest:
        return depot

    return nearest_customer
