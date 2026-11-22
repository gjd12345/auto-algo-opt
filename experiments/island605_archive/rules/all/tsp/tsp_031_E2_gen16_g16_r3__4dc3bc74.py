def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    distances_from_current = distance_matrix[current_node][unvisited_nodes]
    distances_from_dest = distance_matrix[destination_node][unvisited_nodes]

    # Compute local smoothness penalty: linear ratio of candidate edge to mean neighbor distance
    penalties = np.ones_like(distances_from_current, dtype=float)
    for i, node in enumerate(unvisited_nodes):
        neighbor_dists = distance_matrix[node][unvisited_nodes]
        neighbor_dists = neighbor_dists[neighbor_dists > 0]
        if len(neighbor_dists) > 0:
            mean_neighbor = np.mean(neighbor_dists)
            if mean_neighbor > 0:
                penalties[i] = distances_from_current[i] / mean_neighbor

    # Score: exponential scaling of destination distance, divided by penalty
    scores = np.exp(distances_from_dest / (np.max(distances_from_dest) + 1e-10)) / (penalties + 1e-10)

    # For very small remaining sets (<=3), fall back to nearest neighbor
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distances_from_current)]

    return unvisited_nodes[np.argmax(scores)]
