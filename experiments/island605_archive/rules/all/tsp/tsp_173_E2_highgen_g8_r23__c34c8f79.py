def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n_unvisited = len(unvisited_nodes)
    if n_unvisited == 1:
        return unvisited_nodes[0]

    dists = distance_matrix[current_node][unvisited_nodes]
    scores = np.zeros(n_unvisited)

    for i, node in enumerate(unvisited_nodes):
        # Average distance from candidate to all other unvisited nodes
        other_nodes = unvisited_nodes[np.arange(n_unvisited) != i]
        if len(other_nodes) > 0:
            avg_dist_to_others = np.mean(distance_matrix[node][other_nodes])
        else:
            avg_dist_to_others = 0.0

        # Score: ratio of average centrality distance to immediate distance
        # Higher ratio means more central relative to current proximity
        scores[i] = avg_dist_to_others / (dists[i] + 1e-10)

    # Select node with highest score
    return unvisited_nodes[np.argmax(scores)]
