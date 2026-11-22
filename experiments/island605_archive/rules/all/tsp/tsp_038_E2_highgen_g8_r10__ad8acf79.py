def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    dist_from_current = distance_matrix[current_node][unvisited_nodes]
    dist_to_dest = distance_matrix[destination_node][unvisited_nodes]

    min_visited_dist = np.minimum(dist_from_current, dist_to_dest)
    regret = dist_to_dest - min_visited_dist

    score = -0.7 * regret + 0.6 * dist_from_current
    best_idx = np.argmin(score)
    return unvisited_nodes[best_idx]
