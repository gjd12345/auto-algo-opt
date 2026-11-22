def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    # Step 1: Compute regret factor - maximum distance from any unvisited node to destination
    dists_to_dest = distance_matrix[unvisited_nodes][:, destination_node]
    max_dist_to_dest = np.max(dists_to_dest)

    # Step 2: For each candidate, compute score combining regret and smoothness
    best_score = float('inf')
    best_node = unvisited_nodes[0]

    for node in unvisited_nodes:
        d_current = distance_matrix[current_node][node]
        d_to_dest = distance_matrix[node][destination_node]

        # Regret penalty: how much further this node is from destination vs the farthest
        regret = max_dist_to_dest - d_to_dest

        # Smoothness penalty: penalize edges that are long relative to direct distance
        direct_dist = distance_matrix[current_node][destination_node]
        smoothness_penalty = 0
        if d_current > 1.2 * direct_dist:
            smoothness_penalty = d_current * 0.4

        # Composite score: minimize travel + avoid regret + keep smooth
        score = d_current + 0.5 * regret + smoothness_penalty
        if score < best_score:
            best_score = score
            best_node = node

    return best_node
