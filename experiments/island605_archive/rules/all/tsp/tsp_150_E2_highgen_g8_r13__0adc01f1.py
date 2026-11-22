def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dist_curr = distance_matrix[current_node][unvisited_nodes]
    dist_dest = distance_matrix[destination_node][unvisited_nodes]

    scores = np.zeros(len(unvisited_nodes))
    for i, u in enumerate(unvisited_nodes):
        others = unvisited_nodes[unvisited_nodes != u]
        if len(others) > 0:
            dists_to_others = distance_matrix[u][others]
            harmonic_mean = len(others) / np.sum(1.0 / (dists_to_others + 1e-10))
        else:
            harmonic_mean = 1.0

        score = (dist_curr[i] * 0.3 + dist_dest[i] * 0.4 + harmonic_mean * 0.3) / (dist_curr[i] + 1e-10)
        scores[i] = score

    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]
    return unvisited_nodes[np.argmax(scores)]
