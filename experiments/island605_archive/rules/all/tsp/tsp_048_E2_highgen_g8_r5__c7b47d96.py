def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    distances = distance_matrix[current_node][unvisited_nodes]
    dest_distances = distance_matrix[destination_node][unvisited_nodes]

    max_dest = np.max(dest_distances)
    far_score = dest_distances / max_dest if max_dest > 0 else np.zeros_like(dest_distances)

    max_dist = np.max(distances)
    penalty = np.zeros_like(distances, dtype=float)
    for i, node in enumerate(unvisited_nodes):
        neighbor_dists = distance_matrix[node][unvisited_nodes]
        neighbor_dists = neighbor_dists[neighbor_dists > 0]
        if len(neighbor_dists) > 0:
            avg_neighbor = np.mean(neighbor_dists)
            if avg_neighbor > 0:
                ratio = distances[i] / avg_neighbor
                if ratio > 2.0:
                    penalty[i] = ratio * 0.8
                elif ratio > 1.5:
                    penalty[i] = ratio * 0.4

    combined = distances * (1 + penalty) - 0.6 * far_score * max_dist

    return unvisited_nodes[np.argmin(combined)]
