def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    best_node = None
    best_score = -float('inf')

    for node in unvisited_nodes:
        dist_to_current = distance_matrix[current_node][node]
        dist_to_destination = distance_matrix[node][destination_node]

        # Weight farthest from destination (weight 0.3) but heavily penalize long current edge (weight 0.7)
        score = 0.3 * dist_to_destination - 0.7 * dist_to_current

        # Stronger 2-opt-awareness: penalize if edge is >1.5x average local distance
        local_distances = distance_matrix[node][unvisited_nodes]
        local_distances = local_distances[local_distances > 0]
        avg_local = np.mean(local_distances) if len(local_distances) > 0 else 1
        if dist_to_current > 1.5 * avg_local:
            score -= 2 * dist_to_current  # heavier penalty

        if score > best_score:
            best_score = score
            best_node = node

    return best_node
