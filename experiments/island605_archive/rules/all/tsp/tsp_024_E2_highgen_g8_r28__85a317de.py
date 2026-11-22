def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    distances_current = distance_matrix[current_node][unvisited_nodes]
    distances_dest = distance_matrix[destination_node][unvisited_nodes]
    best_score = None
    best_node = None
    for i, candidate in enumerate(unvisited_nodes):
        d_current = distances_current[i]
        d_dest = distances_dest[i]
        other_unvisited = unvisited_nodes[unvisited_nodes != candidate]
        if len(other_unvisited) > 0:
            max_neighbor_dist = np.max(distance_matrix[candidate][other_unvisited])
        else:
            max_neighbor_dist = 0
        # Score: penalize small current distance, reward large destination distance and large farthest neighbor distance
        score = d_current - 0.3 * d_dest - 0.4 * max_neighbor_dist
        if best_score is None or score < best_score:
            best_score = score
            best_node = candidate
    return int(best_node)
