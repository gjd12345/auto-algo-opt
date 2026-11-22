def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    # Compute distances from current node to all unvisited nodes
    dist_from_current = distance_matrix[current_node][unvisited_nodes]

    # Compute distances from destination node to all unvisited nodes (avoid ending with a very long edge)
    dist_from_dest = distance_matrix[destination_node][unvisited_nodes]

    # Penalize nodes that are close to visited ones (encourage early exploration of distant clusters)
    # Use the minimum distance from current node as a proxy for "closeness to visited"
    min_dist_to_visited = np.min(dist_from_current)

    # Score: weight = 0.5 * dist_from_current + 0.3 * (-dist_from_dest) + 0.2 * min_dist_to_visited
    # We want to minimize score; so we want small dist_from_current, large dist_from_dest (negative), and large min_dist_to_visited (positive)
    scores = 0.5 * dist_from_current - 0.3 * dist_from_dest + 0.2 * min_dist_to_visited

    # Fallback to nearest neighbor if only 2 nodes left (to avoid erratic behavior)
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(dist_from_current)]

    return unvisited_nodes[np.argmin(scores)]
