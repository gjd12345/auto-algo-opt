def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Start new route: choose the customer with the highest regret (difference between best and second-best insertion cost)
        best_costs = np.full(len(unvisited_nodes), np.inf)
        second_best_costs = np.full(len(unvisited_nodes), np.inf)
        for i, u in enumerate(unvisited_nodes):
            costs = []
            for v in unvisited_nodes:
                if v == u:
                    continue
                cost = distance_matrix[depot, u] + distance_matrix[u, v] - distance_matrix[depot, v]
                costs.append(cost)
            if costs:
                costs.sort()
                best_costs[i] = costs[0]
                second_best_costs[i] = costs[1] if len(costs) > 1 else costs[0]
        regret = second_best_costs - best_costs
        # Also encourage serving high-demand customers when capacity allows
        demand_ratio = demands[unvisited_nodes] / rest_capacity
        score = regret * (1 + 0.3 * demand_ratio)
        return unvisited_nodes[np.argmax(score)]
    else:
        # Already on route: use a savings-based heuristic
        savings = np.zeros(len(unvisited_nodes))
        for i, u in enumerate(unvisited_nodes):
            # Savings = distance(current, depot) + distance(depot, u) - distance(current, u)
            savings[i] = distance_matrix[current_node, depot] + distance_matrix[depot, u] - distance_matrix[current_node, u]
        # Higher savings is better
        best_idx = np.argmax(savings)
        # Early return if the best saving is negative (meaning returning to depot is better)
        if savings[best_idx] < 0:
            return depot
        return unvisited_nodes[best_idx]
