def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        best_saving = -np.inf
        best_node = unvisited_nodes[0]
        for u in unvisited_nodes:
            base_cost = distance_matrix[depot][u]
            other_nodes = unvisited_nodes[unvisited_nodes != u]
            if len(other_nodes) > 0:
                min_dist_to_other = np.min(distance_matrix[u][other_nodes])
            else:
                min_dist_to_other = 0
            saving = base_cost - min_dist_to_other
            if saving > best_saving:
                best_saving = saving
                best_node = u
        return best_node
    else:
        penalty = distance_matrix[depot][unvisited_nodes] * (1 - rest_capacity / (np.max(demands) + 1))
        scores = distance_matrix[current_node][unvisited_nodes] + penalty
        best_idx = np.argmin(scores)
        return unvisited_nodes[best_idx]
