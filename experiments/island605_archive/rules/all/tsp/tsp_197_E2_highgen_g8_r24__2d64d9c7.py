def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dist_from_current = distance_matrix[current_node][unvisited_nodes]

    # If only one unvisited node remains, return it directly
    if len(unvisited_nodes) == 1:
        return int(unvisited_nodes[0])

    # Compute average edge length of current partial tour (approximated by mean of last two edges)
    if current_node != destination_node:
        last_edge = distance_matrix[current_node][destination_node]
        avg_edge = last_edge
    else:
        avg_edge = np.mean(dist_from_current)

    # Compute spread score: prefer nodes in different direction from existing cluster
    scores = []
    for i, candidate in enumerate(unvisited_nodes):
        d = dist_from_current[i]

        # Detour penalty: how much longer than average edge
        detour_penalty = d / (avg_edge + 1e-10)

        # Spatial spread: cosine distance from current to candidate vs destination direction
        if current_node != destination_node:
            vec_dest = distance_matrix[current_node][destination_node]
            vec_candidate = d
            angle_factor = abs(vec_candidate - vec_dest) / (vec_candidate + vec_dest + 1e-10)
        else:
            angle_factor = 0.0

        # Composite score with random perturbation (deterministic based on node id)
        np.random.seed(candidate)
        random_factor = np.random.uniform(0.9, 1.1)

        score = detour_penalty * random_factor - 0.5 * angle_factor
        scores.append(score)

    best_idx = np.argmin(scores)
    return int(unvisited_nodes[best_idx])
