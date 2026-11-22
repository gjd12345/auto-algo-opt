def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n = len(unvisited_nodes)
    if n == 0:
        return destination_node

    cur_dist = distance_matrix[current_node][unvisited_nodes]
    dest_dist = distance_matrix[destination_node][unvisited_nodes]

    # Compute average distance to all other unvisited nodes for each candidate
    avg_neighbor = np.zeros(n)
    for i in range(n):
        total = 0.0
        count = 0
        for j in range(n):
            if i != j:
                total += distance_matrix[unvisited_nodes[i]][unvisited_nodes[j]]
                count += 1
        avg_neighbor[i] = total / count if count > 0 else 0.0

    epsilon = 1e-10
    # Score: prefer nodes far from destination, but penalize if current->candidate edge is long relative to average neighbor distance
    penalty = cur_dist / (avg_neighbor + epsilon)
    score = dest_dist - 2.0 * penalty  # different weight (2.0 vs 5.0)
    best_idx = np.argmax(score)
    return int(unvisited_nodes[best_idx])
