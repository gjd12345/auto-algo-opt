def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return 0

    if current_node == depot:
        # When starting from depot, pick customer with largest savings relative to depot
        best_node = None
        best_savings = -float('inf')
        for u in unvisited_nodes:
            # Clarke-Wright savings: distance(depot, u) + distance(depot, v) - distance(u, v)
            # Here v is the first customer after depot (we consider returning to depot)
            savings = distance_matrix[depot][u] + distance_matrix[depot][depot] - distance_matrix[u][depot]
            # Actually, for first node after depot, savings is just distance(depot, u) because distance(depot, depot)=0
            # But we use a proxy: we want to start with a customer that is far from depot but also not too far from others
            # Instead, use distance from depot (farthest) as baseline
            dist = distance_matrix[depot][u]
            if dist > best_savings:
                best_savings = dist
                best_node = u
        return best_node if best_node is not None else unvisited_nodes[0]
    else:
        # Regret-based selection: compute savings for each candidate relative to depot
        best_node = None
        best_score = -float('inf')
        for u in unvisited_nodes:
            # Savings = distance(current_node, depot) + distance(depot, u) - distance(current_node, u)
            savings = distance_matrix[current_node][depot] + distance_matrix[depot][u] - distance_matrix[current_node][u]
            # Penalty: if returning to depot from u would be expensive (i.e., large distance from u to depot), penalize slightly
            penalty = 0.1 * distance_matrix[u][depot]
            score = savings - penalty
            if score > best_score:
                best_score = score
                best_node = u
        return best_node if best_node is not None else unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
