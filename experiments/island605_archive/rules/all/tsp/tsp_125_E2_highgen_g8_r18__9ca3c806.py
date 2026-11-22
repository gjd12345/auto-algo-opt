def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_score = -float('inf')
    best_node = None

    current_dists = distance_matrix[current_node][unvisited_nodes]

    for candidate in unvisited_nodes:
        dist = distance_matrix[current_node][candidate]

        # Compute best and second-best alternatives for candidate
        others = unvisited_nodes[unvisited_nodes != candidate]
        if len(others) >= 2:
            cand_dists = distance_matrix[candidate][others]
            sorted_cand = np.sort(cand_dists)
            best_alt = sorted_cand[0]
            second_best_alt = sorted_cand[1]
            regret = second_best_alt - best_alt
        elif len(others) == 1:
            best_alt = distance_matrix[candidate][others[0]]
            regret = 0.0
        else:
            best_alt = 0.0
            regret = 0.0

        # Compute average nearest neighbor distances for penalty
        if len(unvisited_nodes) >= 2:
            sorted_current = np.sort(current_dists)
            current_avg_near = (sorted_current[0] + sorted_current[1]) / 2.0
        else:
            current_avg_near = current_dists[0] if len(unvisited_nodes) == 1 else 0.0

        if len(others) >= 2:
            cand_avg_near = (sorted_cand[0] + sorted_cand[1]) / 2.0
        elif len(others) == 1:
            cand_avg_near = distance_matrix[candidate][others[0]]
        else:
            cand_avg_near = 0.0

        avg_near = (current_avg_near + cand_avg_near) / 2.0
        penalty = dist / avg_near if avg_near > 0 else 1.0

        # Score: regret minus weighted penalty (encourage high regret and low penalty)
        score = regret - 0.5 * penalty

        if score > best_score:
            best_score = score
            best_node = candidate

    if best_node is None:
        best_node = unvisited_nodes[np.argmin(current_dists)]

    return best_node
