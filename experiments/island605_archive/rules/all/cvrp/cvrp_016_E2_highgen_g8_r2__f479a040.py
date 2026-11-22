def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Seed route: farthest from depot
        dists = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists)]
    else:
        # Compute average demand of unvisited nodes (capacity-feasible)
        avg_demand = np.mean(demands[unvisited_nodes]) if len(unvisited_nodes) > 0 else 1.0
        capacity_ratio = rest_capacity / (avg_demand + 1e-10)

        # Phase switch: if capacity is tight (ratio < 2), prefer nearest; else prefer savings
        if capacity_ratio < 2.0:
            # Phase 1: greedy nearest
            cur_dists = distance_matrix[current_node][unvisited_nodes]
            return unvisited_nodes[np.argmin(cur_dists)]
        else:
            # Phase 2: regret-based savings from depot
            cur_dists = distance_matrix[current_node][unvisited_nodes]
            depot_dists = distance_matrix[depot][unvisited_nodes]
            savings = depot_dists - cur_dists
            # Normalize savings
            s_min, s_max = savings.min(), savings.max()
            if s_max > s_min:
                savings_norm = (savings - s_min) / (s_max - s_min)
            else:
                savings_norm = np.zeros_like(savings)
            # Add small perturbation to break ties using distance to current node
            perturbation = 1e-6 * (1.0 / (cur_dists + 1e-10))
            score = savings_norm + perturbation
            return unvisited_nodes[np.argmax(score)]
