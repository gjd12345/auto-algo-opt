def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Starting a new route: choose customer with highest regret (largest savings if added now vs. later)
        best_node = None
        best_regret = -1
        for u in unvisited_nodes:
            # Cost to serve u now from depot
            cost_now = distance_matrix[depot][u]
            # Minimum possible cost to serve u later from depot directly (if skipped now)
            cost_later = distance_matrix[depot][u]  # baseline
            # Regret = cost_later - cost_now, but cost_now is the same; so use distance from depot as proxy for urgency
            # Instead: savings if we serve u now vs. having to do a dedicated trip later:
            # Actually, regret = (distance from depot to u) - (distance from current_node to u)
            # For depot start, current_node = depot, regret = 0 for all -> fallback to farthest
            # So use farthest-first for depot start to seed routes
            dist = distance_matrix[depot][u]
            if dist > best_regret:
                best_regret = dist
                best_node = u
        return best_node if best_node is not None else depot
    else:
        # En route: use regret-based nearest neighbor, where regret = distance from current to u vs. distance from depot to u
        best_node = None
        best_score = float('inf')
        for u in unvisited_nodes:
            # Score = distance from current to u minus distance from depot to u (higher savings = lower score)
            score = distance_matrix[current_node][u] - distance_matrix[depot][u]
            if score < best_score:
                best_score = score
                best_node = u
        return best_node if best_node is not None else depot
