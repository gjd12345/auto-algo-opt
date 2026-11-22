def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Start route: pick customer with highest savings (distance from depot to customer) if feasible
        best_saving = -1
        best_node = depot
        for u in unvisited_nodes:
            if demands[u] > rest_capacity:
                continue
            saving = distance_matrix[depot][u]  # proxy for savings: prefer far customers first
            if saving > best_saving:
                best_saving = saving
                best_node = u
        return best_node
    else:
        # Evaluate each feasible candidate by a composite score: (savings - distance from current - demand penalty)
        best_score = float('inf')
        best_node = depot
        for u in unvisited_nodes:
            if demands[u] > rest_capacity:
                continue
            # Savings: distance from depot to u + distance from current to depot - distance from current to u
            savings = distance_matrix[depot][u] + distance_matrix[current_node][depot] - distance_matrix[current_node][u]
            # Penalty for distance from current node
            dist_penalty = distance_matrix[current_node][u]
            # Penalty for demand (higher demand reduces flexibility)
            demand_penalty = demands[u] / (rest_capacity + 1e-9)
            # Score: lower is better (high savings, low distance, low demand)
            score = -savings + dist_penalty + 0.5 * demand_penalty
            if score < best_score:
                best_score = score
                best_node = u
        # If no feasible customer, return depot
        if best_node == depot:
            return depot
        # Early return if best customer is not significantly better than returning to depot
        return_cost = distance_matrix[current_node][depot]
        best_customer_cost = distance_matrix[current_node][best_node]
        if best_customer_cost > 0.8 * return_cost:
            return depot
        return best_node
