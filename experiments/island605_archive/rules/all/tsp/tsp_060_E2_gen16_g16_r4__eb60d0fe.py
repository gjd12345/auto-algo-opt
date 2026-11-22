def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    # Fallback to nearest neighbor if only one or two nodes left
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    best_node = None
    best_score = float('inf')

    for candidate in unvisited_nodes:
        d_current = distance_matrix[current_node][candidate]
        # Compute average distance from candidate to other unvisited nodes
        other_nodes = unvisited_nodes[unvisited_nodes != candidate]
        if len(other_nodes) > 0:
            avg_other_dist = np.mean(distance_matrix[candidate][other_nodes])
        else:
            avg_other_dist = 0

        # Penalty: if d_current is much larger than the average local distance, penalize
        penalty = d_current / (avg_other_dist + 1e-10)
        # Score: favor close to current node and penalize far from destination
        dist_to_dest = distance_matrix[candidate][destination_node]
        score = d_current + 1.5 * penalty - 0.5 * dist_to_dest

        if score < best_score:
            best_score = score
            best_node = candidate

    return best_node
