def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n_candidates = len(unvisited_nodes)
    if n_candidates == 1:
        return unvisited_nodes[0]

    scores = np.zeros(n_candidates)
    for i, u in enumerate(unvisited_nodes):
        d_current_u = distance_matrix[current_node][u]
        # Average distance from u to all other unvisited nodes plus destination
        other_nodes = np.setdiff1d(unvisited_nodes, [u])
        if len(other_nodes) == 0:
            avg_other_dist = distance_matrix[u][destination_node]
        else:
            avg_other_dist = (np.sum(distance_matrix[u][other_nodes]) + distance_matrix[u][destination_node]) / (len(other_nodes) + 1)
        # Score: reward nodes far from others (spread) minus penalty for long current edge
        scores[i] = avg_other_dist - d_current_u

    # Prefer highest score but add small penalty for very long edges to avoid outliers
    max_score = np.max(scores)
    threshold = 0.2 * max_score if max_score > 0 else 0
    candidates = unvisited_nodes[scores >= (max_score - threshold)]
    return candidates[np.argmin(distance_matrix[current_node][candidates])]
