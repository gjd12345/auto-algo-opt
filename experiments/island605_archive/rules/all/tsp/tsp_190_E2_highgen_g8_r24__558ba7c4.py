def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_score = float('inf')
    best_node = None

    for u in unvisited_nodes:
        direct_cost = distance_matrix[current_node][u]

        # Regret component
        others = unvisited_nodes[unvisited_nodes != u]
        if len(others) > 1:
            dists = distance_matrix[u][others]
            sorted_dists = np.sort(dists)
            best = sorted_dists[0]
            second_best = sorted_dists[1]
            regret = second_best - best
        else:
            regret = 0.0

        # Angular deviation penalty toward destination
        if len(unvisited_nodes) > 1:
            dest_dist = distance_matrix[u][destination_node]
            current_to_dest = distance_matrix[current_node][destination_node] + 1e-8
            deviation_penalty = (direct_cost + dest_dist) / current_to_dest
        else:
            deviation_penalty = 1.0

        # New weighting: high weight on direct cost, high weight on regret, moderate on deviation
        score = 2.0 * direct_cost - 1.5 * regret + 0.8 * deviation_penalty * direct_cost

        if score < best_score:
            best_score = score
            best_node = u

    return best_node
