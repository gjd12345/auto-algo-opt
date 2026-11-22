def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dist_from_current = distance_matrix[current_node][unvisited_nodes]
    dist_to_dest = distance_matrix[destination_node][unvisited_nodes]

    scores = np.zeros(len(unvisited_nodes))
    for i, u in enumerate(unvisited_nodes):
        base = dist_from_current[i]
        bonus = dist_to_dest[i] * 0.7
        other_dists = distance_matrix[u][unvisited_nodes]
        min_other = np.min(other_dists[other_dists > 0]) if len(other_dists) > 1 else 0
        penalty = max(0, dist_from_current[i] - min_other) * 0.5
        scores[i] = base - bonus + penalty

    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(dist_from_current)]

    return unvisited_nodes[np.argmin(scores)]
