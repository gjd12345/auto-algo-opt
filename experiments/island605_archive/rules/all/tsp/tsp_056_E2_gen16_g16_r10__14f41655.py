def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    # Compute distances from current node
    dist_curr = distance_matrix[current_node][unvisited_nodes]
    # Compute distances from destination node
    dist_dest = distance_matrix[destination_node][unvisited_nodes]

    # Normalize both sets to avoid scale bias
    max_curr = dist_curr.max() if dist_curr.max() > 0 else 1
    max_dest = dist_dest.max() if dist_dest.max() > 0 else 1
    norm_curr = dist_curr / max_curr
    norm_dest = dist_dest / max_dest

    # Score: high if close to current (for smoothness) and far from destination (to seed far clusters)
    # Lower score is better (we will argmin)
    score = norm_curr - 0.5 * norm_dest  # tune weight as needed

    # Fallback: if all unvisited is small (<= 2) use pure nearest neighbor
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(dist_curr)]

    # Select node with minimum score
    return unvisited_nodes[np.argmin(score)]
