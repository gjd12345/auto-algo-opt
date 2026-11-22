def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    unvisited = unvisited_nodes
    n_unvisited = len(unvisited)
    if n_unvisited == 1:
        return unvisited[0]

    best_score = -float('inf')
    best_node = unvisited[0]

    for u in unvisited:
        d_current = distance_matrix[current_node][u]
        other = [v for v in unvisited if v != u]
        if len(other) == 0:
            score = 1.0 / (d_current + 1e-10)
        else:
            dists = [distance_matrix[u][v] for v in other]
            mean_dist = sum(dists) / len(dists)
            geo_mean = (np.prod(dists))**(1.0/len(dists))
            variance = sum((d - mean_dist)**2 for d in dists) / len(dists)
            score = (1.0 / (d_current + 1e-10)) * (geo_mean + 1e-10) - 0.1 * variance
        if score > best_score:
            best_score = score
            best_node = u

    return best_node
