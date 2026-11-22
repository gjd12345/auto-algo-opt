def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_score = np.inf
    best_node = unvisited_nodes[0]

    for candidate in unvisited_nodes:
        d = distance_matrix[current_node][candidate]

        others = unvisited_nodes[unvisited_nodes != candidate]
        if len(others) > 0:
            dists_to_others = distance_matrix[candidate][others]
            avg_dist = np.mean(dists_to_others)
            var_dist = np.var(dists_to_others)
            # Score: ratio of current distance to average, plus normalized variance penalty
            score = (d / max(avg_dist, 1e-10)) + 0.2 * (var_dist / max(avg_dist**2, 1e-10))
        else:
            score = d

        if score < best_score:
            best_score = score
            best_node = candidate

    return best_node
