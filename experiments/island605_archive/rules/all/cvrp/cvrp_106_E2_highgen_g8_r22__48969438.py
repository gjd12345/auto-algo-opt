def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Seed phase: prefer farthest from depot among unvisited nodes
        far_idx = np.argmax(distance_matrix[depot][unvisited_nodes])
        return unvisited_nodes[far_idx]

    # Compute regret for each unvisited node
    best_cost = np.full(len(unvisited_nodes), np.inf)
    second_best_cost = np.full(len(unvisited_nodes), np.inf)

    for i, node in enumerate(unvisited_nodes):
        # Cost to go directly from current node
        cost_direct = distance_matrix[current_node][node]
        # Cost to go via depot (return to depot first)
        cost_via_depot = distance_matrix[current_node][depot] + distance_matrix[depot][node]
        # Best and second best costs
        if cost_direct < best_cost[i]:
            second_best_cost[i] = best_cost[i]
            best_cost[i] = cost_direct
        elif cost_direct < second_best_cost[i]:
            second_best_cost[i] = cost_direct
        if cost_via_depot < best_cost[i]:
            second_best_cost[i] = best_cost[i]
            best_cost[i] = cost_via_depot
        elif cost_via_depot < second_best_cost[i]:
            second_best_cost[i] = cost_via_depot

    regret = second_best_cost - best_cost
    # Select node with maximum regret
    max_regret_idx = np.argmax(regret)
    candidate = unvisited_nodes[max_regret_idx]

    # Return to depot if nearest candidate is worse than going back
    if distance_matrix[current_node][candidate] > distance_matrix[current_node][depot]:
        return depot

    return candidate
