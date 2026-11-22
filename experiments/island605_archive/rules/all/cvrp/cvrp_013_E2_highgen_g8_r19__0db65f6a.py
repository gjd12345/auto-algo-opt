def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Regret-based seeding: pick customer with largest gap between best and second-best insertion cost
        best_costs = []
        second_best_costs = []
        for u in unvisited_nodes:
            costs = []
            for v in unvisited_nodes:
                if v == u:
                    continue
                cost = distance_matrix[depot][u] + distance_matrix[u][v] - distance_matrix[depot][v]
                costs.append(cost)
            costs.sort()
            best_costs.append(costs[0] if len(costs) > 0 else float('inf'))
            second_best_costs.append(costs[1] if len(costs) > 1 else float('inf'))
        regrets = [second_best_costs[i] - best_costs[i] for i in range(len(unvisited_nodes))]
        return unvisited_nodes[np.argmax(regrets)]
    else:
        # Savings-based selection: choose customer with largest distance saved vs returning to depot now
        best_savings = -1
        best_node = unvisited_nodes[0]
        for u in unvisited_nodes:
            saving = distance_matrix[current_node][depot] + distance_matrix[depot][u] - distance_matrix[current_node][u]
            if saving > best_savings:
                best_savings = saving
                best_node = u
        return best_node
