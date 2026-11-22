def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    dist_from_current = distance_matrix[current_node][unvisited_nodes]
    dist_from_dest = distance_matrix[destination_node][unvisited_nodes]

    # Avoid division by zero
    dist_from_current_safe = np.where(dist_from_current == 0, 1e-10, dist_from_current)

    # Multiplicative score: product of (distance to dest) * (1 / distance from current)
    raw_score = dist_from_dest / dist_from_current_safe

    # Normalize by the minimum ratio to prevent extreme values from dominating
    min_ratio = np.min(dist_from_dest / dist_from_current_safe)
    if min_ratio > 0:
        score = raw_score / min_ratio
    else:
        score = raw_score

    best_idx = np.argmax(score)
    return unvisited_nodes[best_idx]
