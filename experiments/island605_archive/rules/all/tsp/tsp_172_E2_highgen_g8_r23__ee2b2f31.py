def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n = len(unvisited_nodes)
    if n == 1:
        return unvisited_nodes[0]

    dists_from_current = distance_matrix[current_node][unvisited_nodes]

    # For each candidate, compute total distance to all other unvisited nodes
    total_dist_to_others = np.array([
        np.sum(distance_matrix[u][unvisited_nodes])
        for u in unvisited_nodes
    ])

    # Average distance to other unvisited nodes (excluding itself)
    avg_dist_to_others = (total_dist_to_others - dists_from_current) / (n - 1)

    # Ratio: larger means a node is "more central" relative to its distance from current
    ratio = avg_dist_to_others / (dists_from_current + 1e-10)

    # Prefer high ratio (central and close), fallback to nearest neighbor
    if np.max(ratio) < 1e-6:
        return unvisited_nodes[np.argmin(dists_from_current)]

    return unvisited_nodes[np.argmax(ratio)]
