def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot or len(unvisited_nodes) == 1:
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    # Compute geometric center (mean coordinates) of unvisited nodes
    center_coords = np.mean([distance_matrix[node] for node in unvisited_nodes], axis=0)

    best_idx = None
    best_score = np.inf
    for u in unvisited_nodes:
        dist_to_current = distance_matrix[current_node][u]
        dist_to_center = np.linalg.norm(distance_matrix[u] - center_coords)
        if dist_to_center < 1e-10:
            score = dist_to_current
        else:
            score = dist_to_current / dist_to_center
        if score < best_score:
            best_score = score
            best_idx = u
    return best_idx
