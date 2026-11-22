def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dist_current = distance_matrix[current_node][unvisited_nodes]
    dist_dest = distance_matrix[destination_node][unvisited_nodes]
    farthest_bonus = -0.6 * dist_dest
    avg_neighbor = (dist_current + dist_dest) / 2
    smooth_penalty = 0.2 * (dist_current - avg_neighbor)
    scores = dist_current + farthest_bonus + smooth_penalty
    best_idx = np.argmin(scores)
    return int(unvisited_nodes[best_idx])
