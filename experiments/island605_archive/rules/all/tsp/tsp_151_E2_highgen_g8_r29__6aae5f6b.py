def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dists_current = distance_matrix[current_node][unvisited_nodes]
    dists_dest = distance_matrix[destination_node][unvisited_nodes]

    # Power factor to control far-node promotion (higher = more aggressive)
    power = 0.7

    # Score: current distance / (destination distance ^ power)
    score = dists_current / (dists_dest ** power + 1e-10)

    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(dists_current)]

    return unvisited_nodes[np.argmin(score)]
