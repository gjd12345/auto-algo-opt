def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_score = float('inf')
    best_node = unvisited_nodes[0]

    for u in unvisited_nodes:
        d_cur = distance_matrix[current_node][u]
        d_u_dest = distance_matrix[u][destination_node]

        # Coupling penalty: count how many other unvisited nodes have u as their nearest neighbor among all unvisited nodes
        coupling_count = 0
        for v in unvisited_nodes:
            if v != u:
                nearest_dist = min(distance_matrix[v][w] for w in unvisited_nodes if w != v)
                if distance_matrix[v][u] == nearest_dist:
                    coupling_count += 1

        # Penalty: normalized coupling fraction times a scaling factor
        max_possible_coupling = len(unvisited_nodes) - 1
        coupling_penalty = (coupling_count / max_possible_coupling) * 0.4 * d_u_dest

        score = d_cur + coupling_penalty

        if score < best_score:
            best_score = score
            best_node = u

    return best_node
