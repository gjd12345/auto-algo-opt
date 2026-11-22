def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot and len(unvisited_nodes) > 0:
        distances_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(distances_from_depot)]
    elif len(unvisited_nodes) == 0:
        return depot
    else:
        best_score = -np.inf
        best_node = unvisited_nodes[0]
        for node in unvisited_nodes:
            if demands[node] > rest_capacity:
                continue
            d_cur = distance_matrix[current_node][node]
            d_depot = distance_matrix[depot][node]
            savings = distance_matrix[depot][current_node] + d_depot - distance_matrix[current_node][node]
            regret = 0.0
            for other in unvisited_nodes:
                if other == node or demands[other] > rest_capacity:
                    continue
                s_other = distance_matrix[depot][current_node] + distance_matrix[depot][other] - distance_matrix[current_node][other]
                if s_other > regret:
                    regret = s_other
            regret = max(regret - savings, 0.0)
            score = -d_cur - 0.5 * regret
            if score > best_score:
                best_score = score
                best_node = node
        return best_node
