def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n = len(unvisited_nodes)
    if n == 0:
        return destination_node
    if n == 1:
        return unvisited_nodes[0]

    dists = distance_matrix[current_node][unvisited_nodes]
    min_dist = np.min(dists)

    best_node = unvisited_nodes[np.argmin(dists)]
    best_score = -float('inf')

    for i, node in enumerate(unvisited_nodes):
        # Current edge cost relative to minimum possible from current
        current_ratio = dists[i] / (min_dist + 1e-10)

        # Connectivity sparsity: average distance from this node to all other unvisited nodes
        other_dists = [distance_matrix[node][other] for other in unvisited_nodes if other != node]
        if other_dists:
            avg_other_dist = np.mean(other_dists)
        else:
            avg_other_dist = distance_matrix[node][destination_node]

        # Score: favor low current ratio but high average distance (sparsity)
        score = avg_other_dist / (current_ratio + 1e-10)

        if score > best_score:
            best_score = score
            best_node = node

    return best_node
