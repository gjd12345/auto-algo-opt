def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dist_from_current = distance_matrix[current_node][unvisited_nodes]
    dist_from_dest = distance_matrix[destination_node][unvisited_nodes]

    # Score favoring nodes that are close to current but far from destination (to avoid early detours)
    # and penalizing high angular deviation from straight line to destination
    score = dist_from_current - 0.5 * dist_from_dest

    # Add small penalty for nodes that create a large angle relative to destination direction
    # Estimate using distances: if current->candidate is much larger than current->destination, penalize
    dest_dist = distance_matrix[current_node][destination_node]
    for i, u in enumerate(unvisited_nodes):
        if dist_from_current[i] > 1.5 * dest_dist and dest_dist > 0:
            score[i] += 0.3 * (dist_from_current[i] - dest_dist)

    return int(unvisited_nodes[np.argmin(score)])
