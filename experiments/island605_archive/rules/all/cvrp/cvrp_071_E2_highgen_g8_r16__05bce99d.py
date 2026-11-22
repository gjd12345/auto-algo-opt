def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    if current_node == depot:
        # Weighted composite: distance from depot + regret + capacity utilization bonus
        best_score = -1e9
        best_node = unvisited_nodes[0]
        for u in unvisited_nodes:
            dist_depot_u = distance_matrix[depot][u]
            # Regret: cost difference between nearest alternative and direct from depot
            best_other = np.inf
            for v in unvisited_nodes:
                if v != u:
                    cost = min(distance_matrix[depot][v] + distance_matrix[v][u],
                               distance_matrix[depot][u] + distance_matrix[u][v])
                    if cost < best_other:
                        best_other = cost
            if best_other == np.inf:
                best_other = dist_depot_u
            regret = best_other - dist_depot_u
            # Capacity utilization bonus: prefer customers that fill the vehicle better
            capacity_ratio = demands[u] / max(rest_capacity, 1e-6)
            bonus = 1.0 / (1.0 + capacity_ratio)  # small demand gets higher bonus
            # Combined score: 0.5*dist + 0.3*regret + 0.2*bonus
            score = 0.5 * dist_depot_u + 0.3 * regret + 0.2 * bonus * dist_depot_u
            if score > best_score:
                best_score = score
                best_node = u
        return best_node
    else:
        # En route: nearest neighbor with dynamic savings based on remaining capacity
        best_score = -1e9
        best_node = unvisited_nodes[0]
        for u in unvisited_nodes:
            cost_direct = distance_matrix[current_node][u]
            cost_via_depot = distance_matrix[current_node][depot] + distance_matrix[depot][u]
            savings = cost_via_depot - cost_direct
            # Adjust savings weight by remaining capacity fraction
            cap_factor = rest_capacity / 100.0  # normalized (assumes max capacity ~100)
            score = -cost_direct + max(0.1, min(0.5, cap_factor)) * savings
            if score > best_score:
                best_score = score
                best_node = u
        return best_node
