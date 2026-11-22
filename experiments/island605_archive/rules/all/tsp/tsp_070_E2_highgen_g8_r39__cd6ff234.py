def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dists_current = distance_matrix[current_node][unvisited_nodes]
    dists_dest = distance_matrix[destination_node][unvisited_nodes]

    proximity_factor = np.min(dists_dest) / (dists_dest + 1e-10)

    penalty = np.ones_like(dists_current)
    for i, candidate in enumerate(unvisited_nodes):
        other_dists = distance_matrix[candidate][unvisited_nodes]
        median_dist = np.median(other_dists)
        ratio = dists_current[i] / (median_dist + 1e-10)
        penalty[i] = ratio

    combined = dists_current * penalty * proximity_factor
    return unvisited_nodes[np.argmin(combined)]
