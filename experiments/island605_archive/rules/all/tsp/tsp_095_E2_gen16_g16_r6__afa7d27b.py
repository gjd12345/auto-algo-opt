def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    # Compute base distances from current node to all unvisited nodes
    current_distances = distance_matrix[current_node][unvisited_nodes]

    # Nearest score: prefer nodes close to current node (normalized)
    max_curr_dist = current_distances.max()
    nearest_score = 1 - (current_distances / max_curr_dist) if max_curr_dist > 0 else 0

    # Farthest-from-destination score: prefer nodes far from destination (normalized)
    dest_distances = distance_matrix[destination_node][unvisited_nodes]
    max_dest_dist = dest_distances.max()
    farthest_dest_score = dest_distances / max_dest_dist if max_dest_dist > 0 else 0

    # Combined score: weight nearest more heavily, add farthest-from-destination bonus
    alpha = 0.7  # weight for nearest to current
    beta = 0.3   # weight for farthest from destination
    combined_score = alpha * nearest_score + beta * farthest_dest_score

    # Pick the node with highest combined score
    best_idx = np.argmax(combined_score)
    return int(unvisited_nodes[best_idx])
