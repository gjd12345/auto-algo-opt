def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    # Compute base distances from current node to all unvisited nodes
    distances = distance_matrix[current_node][unvisited_nodes]

    # Farthest-insertion component: prefer nodes farther from the destination
    dest_distances = distance_matrix[destination_node][unvisited_nodes]
    farthest_penalty = dest_distances / (dest_distances.max() + 1e-9)

    # 2-opt awareness: penalize edges that are locally long compared to neighbors
    avg_neighbor_dist = np.array([
        np.mean(np.sort(distance_matrix[node][distance_matrix[node] > 0])[:5])
        for node in unvisited_nodes
    ])
    edge_ratio = distances / (avg_neighbor_dist + 1e-9)

    # Combined score: lower is better (trade-off between far-priority and smoothness)
    alpha = 0.6  # weight for farthest strategy
    beta = 0.4   # weight for smoothness
    scores = alpha * (1 - farthest_penalty) + beta * edge_ratio

    # Select node with minimal score
    best_idx = np.argmin(scores)
    return int(unvisited_nodes[best_idx])
