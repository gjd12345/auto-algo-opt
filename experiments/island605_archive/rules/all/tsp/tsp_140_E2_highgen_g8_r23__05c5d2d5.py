def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    distances = distance_matrix[current_node][unvisited_nodes]
    dest_distances = distance_matrix[unvisited_nodes][:, destination_node]

    # Compute angular deviation using cosine similarity via dot product proxy
    # We approximate angle by ratio of direct distance vs path through candidate
    direct_to_dest = distance_matrix[current_node][destination_node]

    scores = []
    for i, node in enumerate(unvisited_nodes):
        d = distances[i]
        # Path cost if going through this node to destination
        path_cost = d + dest_distances[i]
        # Deviation factor: how much longer the path is vs direct
        deviation = abs(path_cost - direct_to_dest) / (direct_to_dest + 1e-10)
        # Diversity weight: variance of distances among all candidates
        variance = np.var(distances) + 1e-10
        weight = 1.0 / (1.0 + deviation)
        score = d * weight * (1.0 + np.log1p(variance))
        scores.append(score)

    # Select node minimizing the weighted score (prefer low distance, high deviation)
    return unvisited_nodes[np.argmin(scores)]
