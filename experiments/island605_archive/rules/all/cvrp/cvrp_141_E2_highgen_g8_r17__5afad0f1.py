def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    n = len(unvisited_nodes)
    if n == 0:
        return depot
    if current_node == depot and n == 1:
        return unvisited_nodes[0]

    best_score = -float('inf')
    best_node = unvisited_nodes[0]

    for u in unvisited_nodes:
        d_cur = distance_matrix[current_node, u]
        d_dep = distance_matrix[depot, u]

        # Insertion cost and alternative cost
        insertion_cost = d_cur + d_dep - distance_matrix[current_node, depot]
        alt_cost = distance_matrix[depot, u]
        regret = abs(insertion_cost - alt_cost)

        # New parameter settings: heavy penalty on distance from depot, reward proximity to current node
        weight_regret = 0.2
        weight_dist_from_cur = 0.5
        weight_dist_from_dep = 0.3

        score = (weight_regret * regret
                 - weight_dist_from_cur * d_cur
                 + weight_dist_from_dep * d_dep)

        if score > best_score:
            best_score = score
            best_node = u

    return best_node
