def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot or len(unvisited_nodes) == 0:
        distances_from_depot = distance_matrix[depot, unvisited_nodes]
        farthest_idx = np.argmax(distances_from_depot)
        return unvisited_nodes[farthest_idx]

    dist_from_current = distance_matrix[current_node, unvisited_nodes]
    dist_from_depot = distance_matrix[depot, unvisited_nodes]

    # Weighted score: 0.3 * normalized distance from depot + 0.7 * normalized distance from current
    max_cur = np.max(dist_from_current) if len(dist_from_current) > 0 else 1
    max_dep = np.max(dist_from_depot) if len(dist_from_depot) > 0 else 1

    score = 0.3 * (dist_from_depot / max_dep) + 0.7 * (1 - dist_from_current / max_cur)
    return unvisited_nodes[np.argmax(score)]
