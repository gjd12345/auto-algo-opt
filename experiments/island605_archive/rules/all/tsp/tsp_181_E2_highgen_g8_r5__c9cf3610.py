def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    distances = distance_matrix[current_node][unvisited_nodes]
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]
    penalties = np.zeros(len(unvisited_nodes))
    for i, u in enumerate(unvisited_nodes):
        other_unvisited = unvisited_nodes[unvisited_nodes != u]
        if len(other_unvisited) > 0:
            avg_dist = np.mean(distance_matrix[u][other_unvisited])
            penalties[i] = distances[i] / (avg_dist + 1e-10)
        else:
            penalties[i] = distances[i]
    scores = distances * 0.3 + penalties * 0.7
    return unvisited_nodes[np.argmin(scores)]
