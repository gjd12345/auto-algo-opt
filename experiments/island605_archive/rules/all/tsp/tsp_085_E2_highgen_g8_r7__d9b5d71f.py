def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    dist_cur = distance_matrix[current_node][unvisited_nodes]
    dist_dest = distance_matrix[unvisited_nodes][:, destination_node]

    # Parameter: weight for balancing current distance vs destination distance
    alpha = 0.3  # lower alpha gives more weight to avoiding far destinations
    epsilon = 1e-10

    scores = (1 - alpha) * dist_cur - alpha * dist_dest
    min_score_idx = np.argmin(scores)
    return unvisited_nodes[min_score_idx]
