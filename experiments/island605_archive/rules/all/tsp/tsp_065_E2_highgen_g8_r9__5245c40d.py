def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    dist_current = distance_matrix[current_node][unvisited_nodes]
    dist_dest = distance_matrix[destination_node][unvisited_nodes]

    # Score: prefer nodes close to current but far from destination,
    # penalized by the sum of both distances to avoid extremely far nodes
    score = (dist_dest - dist_current) - 0.3 * (dist_current + dist_dest)

    best_idx = np.argmax(score)
    return unvisited_nodes[best_idx]
