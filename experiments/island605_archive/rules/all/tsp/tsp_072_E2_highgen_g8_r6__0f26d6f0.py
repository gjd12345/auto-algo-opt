def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_node = None
    best_score = float('inf')
    for u in unvisited_nodes:
        d_cur = distance_matrix[current_node][u]
        other_dists = [distance_matrix[u][v] for v in unvisited_nodes if v != u]
        if len(other_dists) == 0:
            geo_mean = 1.0
        else:
            log_sum = sum(np.log(d + 1e-10) for d in other_dists)
            geo_mean = np.exp(log_sum / len(other_dists))
        score = d_cur / (geo_mean + 1e-10)
        if score < best_score:
            best_score = score
            best_node = u
    if best_node is None:
        best_node = unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
    return int(best_node)
