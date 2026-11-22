def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_node = unvisited_nodes[0]
    best_score = -float('inf')

    for u in unvisited_nodes:
        dist_current_u = distance_matrix[current_node][u]
        other_unvisited = [v for v in unvisited_nodes if v != u]
        if len(other_unvisited) == 0:
            avg_other = 1.0
        else:
            avg_other = np.mean([distance_matrix[u][v] for v in other_unvisited])
        # Score: high when current step is cheap and u is centrally located among remaining nodes
        score = avg_other / (dist_current_u + 1e-10)
        if score > best_score:
            best_score = score
            best_node = u

    # Fallback to nearest neighbor if no improvement over direct greed
    if best_score <= 0:
        best_node = unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    return int(best_node)
