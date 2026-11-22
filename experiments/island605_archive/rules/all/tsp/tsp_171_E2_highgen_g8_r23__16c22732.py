def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n_unvisited = len(unvisited_nodes)
    if n_unvisited == 1:
        return unvisited_nodes[0]

    dists = distance_matrix[current_node][unvisited_nodes]
    best_score = -1
    best_node = unvisited_nodes[0]

    for i, u in enumerate(unvisited_nodes):
        d_current_u = dists[i]
        if d_current_u == 0:
            return u

        avg_dist_to_others = np.mean(distance_matrix[u][unvisited_nodes])
        score = avg_dist_to_others / d_current_u

        if score > best_score:
            best_score = score
            best_node = u

    return best_node
