def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_score = float('inf')
    best_node = unvisited_nodes[0]

    for u in unvisited_nodes:
        dist = distance_matrix[current_node][u]
        others = unvisited_nodes[unvisited_nodes != u]
        if len(others) > 0:
            dists_to_others = distance_matrix[u][others]
            # Geometric mean of distances to other unvisited nodes
            log_mean = np.mean(np.log(dists_to_others + 1e-10))
            geo_mean = np.exp(log_mean)
            # Ratio: penalize long edges relative to candidate's connectivity
            ratio = dist / (geo_mean + 1e-10)
        else:
            ratio = dist  # fallback to nearest neighbor

        if ratio < best_score:
            best_score = ratio
            best_node = u

    return best_node
