def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    if current_node == depot:
        # Start route: pick the node with maximum distance from depot
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]
    else:
        # Compute ratio: distance(current, u)^2 / distance(depot, u)
        dist_current = distance_matrix[current_node][unvisited_nodes]
        dist_depot = distance_matrix[depot][unvisited_nodes]
        # Avoid division by zero; depot has zero distance to itself, but depot not in unvisited_nodes
        scores = np.where(dist_depot > 0, dist_current ** 2 / dist_depot, np.inf)
        # Tie-break with smallest index
        best_idx = unvisited_nodes[np.argmin(scores)]
        return best_idx
