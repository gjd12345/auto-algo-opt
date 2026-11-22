def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n = len(unvisited_nodes)
    if n == 1:
        return unvisited_nodes[0]

    # Compute base distances from current node to each unvisited node
    distances = distance_matrix[current_node][unvisited_nodes]

    # Compute regret for each unvisited node (lookahead one step)
    regrets = np.zeros(n)
    for i, u in enumerate(unvisited_nodes):
        # Distances from u to all other unvisited nodes
        to_others = distance_matrix[u][unvisited_nodes]
        # Exclude distance to itself (zero)
        sorted_dists = np.sort(to_others[to_others > 0])
        if len(sorted_dists) >= 2:
            best = sorted_dists[0]
            second_best = sorted_dists[1]
            regrets[i] = second_best - best
        else:
            regrets[i] = 0

    # Score: prefer low current distance but high regret (weighted)
    alpha = 0.7  # weight for current distance
    beta = 0.3   # weight for regret
    scores = alpha * distances - beta * regrets  # minimize scores

    best_idx = np.argmin(scores)
    return unvisited_nodes[best_idx]
