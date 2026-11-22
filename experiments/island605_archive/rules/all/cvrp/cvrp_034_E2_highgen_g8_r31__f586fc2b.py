def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # At depot: pick the customer with the largest saving of combining depot->u->depot relative to its demand
        savings = np.zeros(len(unvisited_nodes))
        for i, u in enumerate(unvisited_nodes):
            direct_round = 2 * distance_matrix[depot][u]
            demand_penalty = demands[u] / (rest_capacity + 1e-8)
            savings[i] = direct_round / (1 + demand_penalty)
        return unvisited_nodes[np.argmax(savings)]
    else:
        best_idx = None
        best_score = -float('inf')
        for u in unvisited_nodes:
            # Savings: (distance from current to depot + depot to u) - (distance from current to u)
            saving = distance_matrix[current_node][depot] + distance_matrix[depot][u] - distance_matrix[current_node][u]
            # Weight by capacity utilization: prefer customers that leave more capacity for later
            demand_factor = demands[u] / (rest_capacity + 1e-8)
            score = saving - demand_factor * distance_matrix[current_node][u]
            if score > best_score:
                best_score = score
                best_idx = u
        if best_idx is None:
            return depot
        # Early return if no positive saving
        if distance_matrix[current_node][depot] < distance_matrix[current_node][best_idx]:
            return depot
        return best_idx
