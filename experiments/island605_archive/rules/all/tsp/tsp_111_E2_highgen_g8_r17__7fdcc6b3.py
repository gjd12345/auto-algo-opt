def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        # Fallback: farthest insertion for small remaining sets
        from_dest = distance_matrix[destination_node][unvisited_nodes]
        return unvisited_nodes[np.argmax(from_dest)]

    from_current = distance_matrix[current_node][unvisited_nodes]
    from_dest = distance_matrix[destination_node][unvisited_nodes]

    # Farthest priority: prefer nodes farther from destination
    farthest_score = from_dest / (from_current + 1e-9)

    # Nearest-neighbor bias: prefer shorter current edges
    nearest_bias = from_current / (np.min(from_current) + 1e-9)

    # Combine: higher farthest_score is better, lower nearest_bias is better
    combined = -0.7 * farthest_score + 0.3 * nearest_bias

    idx = np.argmin(combined + 1e-10 * np.arange(len(unvisited_nodes)))
    return unvisited_nodes[idx]
