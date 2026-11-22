def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_overall = -float('inf')
    best_node = unvisited_nodes[0]

    for u in unvisited_nodes:
        # Nearest neighbor cost
        cost = distance_matrix[current_node][u]

        # Regret calculation: look at best and second best insertion for u
        best = float('inf')
        second_best = float('inf')
        for v in unvisited_nodes:
            if v == u:
                continue
            # Consider inserting u between v and its neighbors (simplified: just costs from v)
            c = distance_matrix[v][u]
            if c < best:
                second_best = best
                best = c
            elif c < second_best:
                second_best = c
        # Fallback if not enough alternatives
        regret = (second_best - best) if second_best != float('inf') else 0

        # 2-opt awareness penalty: penalize if current->u is much longer than local average
        local_avg = 0.0
        count = 0
        for v in unvisited_nodes:
            if v != u:
                local_avg += distance_matrix[current_node][v]
                count += 1
        if count > 0:
            local_avg /= count
        penalty = max(0, cost - local_avg * 1.5)  # moderate penalty for long edges

        # Combined score: prefer high regret, low cost, low penalty
        score = regret - cost - penalty

        if score > best_overall:
            best_overall = score
            best_node = u

    return best_node
