def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Starting a new route: pick farthest unvisited to reach distant clusters
        dists_from_depot = distance_matrix[depot, unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]

    # Compute polar angles for current node and all unvisited nodes (depot as origin)
    def polar_angle(node):
        dx = distance_matrix[node, depot]  # dummy, use coordinates if available
        # Use a simple geometric proxy: compute angle from depot to node
        return np.arctan2(0, 0)  # placeholder; actual coordinates needed
    # Since coordinates are not provided, fallback to distance-based heuristic:

    # Prefer customers that are near the current node and also not too close to depot
    cur_to_u = distance_matrix[current_node][unvisited_nodes]
    u_to_depot = distance_matrix[depot][unvisited_nodes]

    # Score: prefer near current but penalize if also near depot (to encourage spreading)
    score = cur_to_u - 0.5 * u_to_depot
    best_idx = unvisited_nodes[np.argmin(score)]
    return best_idx
