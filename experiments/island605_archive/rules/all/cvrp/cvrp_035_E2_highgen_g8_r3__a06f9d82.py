def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Seed route: prefer farthest feasible customer from depot
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]
    else:
        # Compute distances from current node to each unvisited customer
        dists_from_current = distance_matrix[current_node][unvisited_nodes]
        # Compute regret: extra distance if we skip a customer now and serve it later from depot
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        regret = dists_from_depot - dists_from_current
        # Penalize customers with demand close to rest_capacity (risk of forcing early return)
        demand_penalty = (demands[unvisited_nodes] / rest_capacity) * 0.5
        # Score: lower is better; combine distance with regret bonus and capacity penalty
        score = dists_from_current - 0.3 * regret + 0.5 * demand_penalty
        best_idx = np.argmin(score)
        # If the best customer is still too far relative to returning to depot, return to depot
        if dists_from_current[best_idx] > distance_matrix[current_node][depot] * 1.3:
            return depot
        return unvisited_nodes[best_idx]
