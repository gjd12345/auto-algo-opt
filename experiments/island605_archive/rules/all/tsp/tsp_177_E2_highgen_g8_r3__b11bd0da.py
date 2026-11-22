def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    # Compute distances from current node to all unvisited nodes
    distances_from_current = distance_matrix[current_node][unvisited_nodes]
    # Compute distances from destination to all unvisited nodes (proxy for cluster farness)
    distances_from_dest = distance_matrix[destination_node][unvisited_nodes]

    # Calculate local average distance from current node to all unvisited nodes
    local_avg = np.mean(distances_from_current)

    # Score: favor nodes far from destination (farthest-insertion), penalize nodes with long current edge (2-opt awareness)
    # Weighted combination: alpha * distance_from_dest - beta * distance_from_current / local_avg
    alpha = 0.6
    beta = 0.4
    scores = alpha * distances_from_dest - beta * (distances_from_current / (local_avg + 1e-10))

    # Select node with maximum score
    best_idx = np.argmax(scores)
    return int(unvisited_nodes[best_idx])
