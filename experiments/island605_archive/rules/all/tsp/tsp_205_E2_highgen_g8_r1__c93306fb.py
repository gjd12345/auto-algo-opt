def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n_remaining = len(unvisited_nodes)
    alpha = 0.7
    beta = 0.2
    gamma = 0.1

    best_node = None
    best_score = -float('inf')

    for node in unvisited_nodes:
        cur_dist = distance_matrix[current_node][node]
        dest_dist = distance_matrix[destination_node][node]

        costs = []
        for other in unvisited_nodes:
            if other != node:
                cost = distance_matrix[node][other]
                costs.append(cost)
        if len(costs) >= 2:
            costs.sort()
            best = costs[0]
            second_best = costs[1]
            regret = second_best - best
        elif len(costs) == 1:
            regret = 0.0
        else:
            regret = 0.0

        score = -alpha * cur_dist - beta * dest_dist + gamma * regret
        if score > best_score:
            best_score = score
            best_node = node

    return best_node
