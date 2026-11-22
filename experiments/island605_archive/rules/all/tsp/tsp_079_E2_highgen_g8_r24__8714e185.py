def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    best_score = float('inf')
    best_node = None
    curr_dists = distance_matrix[current_node][unvisited_nodes]

    for i, node in enumerate(unvisited_nodes):
        direct_dist = curr_dists[i]

        # Average distance from candidate to all other unvisited nodes
        other_mask = unvisited_nodes != node
        other_dists = distance_matrix[node][unvisited_nodes[other_mask]]
        avg_other = np.mean(other_dists) if len(other_dists) > 0 else 0

        # Distance to destination
        dest_dist = distance_matrix[node][destination_node]

        # Score: prefer moderate direct distance, reward high average other (exploration),
        # penalize being too close to destination early
        score = direct_dist - 0.6 * avg_other + 0.4 * (1 - (dest_dist / (np.max(distance_matrix) + 1e-8)))

        if score < best_score:
            best_score = score
            best_node = node

    return best_node
