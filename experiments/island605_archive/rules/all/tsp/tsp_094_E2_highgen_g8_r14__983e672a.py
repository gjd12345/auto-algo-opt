def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    distances = distance_matrix[current_node][unvisited_nodes]

    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    dest_distances = distance_matrix[destination_node][unvisited_nodes]

    mean_local_dist = np.mean(distances)
    penalty = np.where(distances > 1.5 * mean_local_dist, 2.0, 1.0)

    max_dist = np.max(distances) if np.max(distances) > 0 else 1
    norm_dist = distances / max_dist
    max_dest = np.max(dest_distances) if np.max(dest_distances) > 0 else 1
    norm_dest = dest_distances / max_dest

    nearest_weight = 0.7
    furthest_weight = 0.3

    score = nearest_weight * norm_dist - furthest_weight * norm_dest + 0.2 * (1 - penalty)
    score *= penalty

    next_idx = np.argmin(score)
    return unvisited_nodes[next_idx]
