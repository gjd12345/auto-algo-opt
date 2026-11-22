def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Start route: pick the farthest customer to seed distant cluster
        far_idx = np.argmax(distance_matrix[depot][unvisited_nodes])
        return unvisited_nodes[far_idx]
    else:
        best_node = None
        best_score = -np.inf
        for u in unvisited_nodes:
            # Angular deviation from current node (relative to depot)
            angle_u = np.arctan2(distance_matrix[depot][u], 1)
            angle_cur = np.arctan2(distance_matrix[depot][current_node], 1)
            angle_diff = abs(angle_u - angle_cur)
            # Distance from current node
            dist_cur = distance_matrix[current_node][u]
            # Distance from depot
            dist_depot = distance_matrix[depot][u]
            # Composite score: moderate penalty on angle deviation,
            # high reward for closeness to current node, small reward for high depot distance
            score = -0.3 * angle_diff - 0.9 * dist_cur + 0.1 * dist_depot
            if score > best_score:
                best_score = score
                best_node = u
        # Return to depot only if the best candidate is strictly worse than going back
        if best_node is None or distance_matrix[current_node][best_node] > distance_matrix[current_node][depot]:
            return depot
        return best_node
