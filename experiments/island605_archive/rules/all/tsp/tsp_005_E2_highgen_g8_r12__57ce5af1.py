def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    # Compute centroid of unvisited nodes
    unvisited_coords = np.array([(i, distance_matrix[current_node][i]) for i in unvisited_nodes])  # dummy for coordinates
    # In practice, we need actual coordinates; here we approximate using distances to current_node.
    # Better: use node indices as proxy for coordinates if not available.
    # Since coordinates not given, use simple angular proxy: prefer nodes that are "ahead" relative to destination direction.

    # Direction from current to destination
    if current_node == destination_node:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    best_node = None
    best_angle = np.inf

    for u in unvisited_nodes:
        # Use cosine-similarity-like measure: large distance to current and small distance to destination
        d_cur_u = distance_matrix[current_node][u]
        d_dest_u = distance_matrix[destination_node][u]
        # Score: balance between moving away from current and toward destination
        score = d_cur_u - 0.5 * d_dest_u
        if score < best_angle:
            best_angle = score
            best_node = u

    return best_node
