def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_score = float('-inf')
    best_node = unvisited_nodes[0]
    for u in unvisited_nodes:
        d_current_u = distance_matrix[current_node][u]
        d_u_dest = distance_matrix[u][destination_node]
        d_current_dest = distance_matrix[current_node][destination_node]
        # Triangle inequality penalty: how much extra distance adding u costs now vs going directly to destination
        triangle_penalty = d_current_u + d_u_dest - d_current_dest
        # Regret: difference between second-best and best connection to u from any unvisited node (excluding current)
        best_other = float('inf')
        second_best = float('inf')
        for v in unvisited_nodes:
            if v != u:
                cost = distance_matrix[v][u]
                if cost < best_other:
                    second_best = best_other
                    best_other = cost
                elif cost < second_best:
                    second_best = cost
        if second_best == float('inf'):
            second_best = best_other if best_other != float('inf') else d_current_u
        regret = second_best - d_current_u
        # Score: high regret is good, high triangle penalty is bad
        score = regret - triangle_penalty * 0.15
        if score > best_score:
            best_score = score
            best_node = u
    return best_node
