def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    distances_current = distance_matrix[current_node][unvisited_nodes]
    distances_dest = distance_matrix[destination_node][unvisited_nodes]

    max_cur = np.max(distances_current)
    max_dest = np.max(distances_dest)
    min_cur = np.min(distances_current[distances_current > 0])

    best_score = float('inf')
    best_node = unvisited_nodes[0]

    for i, node in enumerate(unvisited_nodes):
        d_cur = distances_current[i]
        d_dest = distances_dest[i]

        # Normalize distances
        norm_cur = d_cur / (max_cur + 1e-8)
        norm_dest = d_dest / (max_dest + 1e-8)

        # Local continuity: prefer not too close to current (avoid backtracking)
        local_factor = max(0, norm_cur - (min_cur / (max_cur + 1e-8)))

        # Global spread: favor nodes farther from destination to seed far areas
        spread_factor = 1.0 - norm_dest

        # Combined score: lower is better
        score = 0.6 * local_factor + 0.4 * spread_factor

        if score < best_score:
            best_score = score
            best_node = node

    return best_node
