def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n = len(unvisited_nodes)
    if n <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    dists_current = distance_matrix[current_node][unvisited_nodes]
    dists_dest = distance_matrix[destination_node][unvisited_nodes]

    scores = []
    for i, node in enumerate(unvisited_nodes):
        d_curr = dists_current[i]
        d_dest = dists_dest[i]

        # Compute average distance from this node to all other unvisited nodes (except itself)
        other_dists = distance_matrix[node][unvisited_nodes]
        # Exclude the distance to itself (zero) by summing and dividing by (n-1)
        avg_separation = (np.sum(other_dists) - d_curr) / (n - 1)

        # Score: current distance + bonus that rewards large destination distance AND large average separation
        # This encourages visiting far-flung nodes early, especially those isolated from other unvisited nodes.
        bonus = d_dest * avg_separation
        score = d_curr - 0.3 * bonus
        scores.append(score)

    best_idx = np.argmin(scores)
    return unvisited_nodes[best_idx]
