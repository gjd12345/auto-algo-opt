def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    # Compute distances from current node to each unvisited node
    dists_from_current = distance_matrix[current_node][unvisited_nodes]
    # Compute distances from each unvisited node to destination node
    dists_to_destination = distance_matrix[destination_node][unvisited_nodes]
    # Score: favor lower current distance (to avoid long jumps) but also favor higher distance to destination (to visit far nodes early)
    # Use a penalty for very long current edges by scaling, and reward far-from-destination nodes
    scores = dists_from_current - 0.5 * dists_to_destination
    # Fallback: nearest neighbor if all scores equal (not likely)
    return unvisited_nodes[np.argmin(scores)]
