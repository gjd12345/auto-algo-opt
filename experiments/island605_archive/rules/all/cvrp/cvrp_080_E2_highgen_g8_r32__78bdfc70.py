def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    unvisited = unvisited_nodes.tolist()
    best_node = None
    best_score = -float('inf')

    for candidate in unvisited:
        if current_node == depot:
            # At depot: prioritize customers with high "regret" (penalty for not serving now)
            costs = []
            for other in unvisited:
                if other != candidate:
                    costs.append(distance_matrix[depot][other])
            if costs:
                min1 = min(costs)
                costs.remove(min1)
                min2 = min(costs) if costs else min1
                regret = min2 - min1
            else:
                regret = 0
            score = regret * 0.6 + distance_matrix[depot][candidate] * 0.4
        else:
            # En route: use regret of inserting candidate into current position vs. best alternative
            direct = distance_matrix[current_node][candidate]
            best_alt = float('inf')
            for other in unvisited:
                if other != candidate:
                    alt = distance_matrix[current_node][other]
                    if alt < best_alt:
                        best_alt = alt
            regret = best_alt - direct if best_alt != float('inf') else 0
            savings = distance_matrix[current_node][depot] + distance_matrix[depot][candidate] - distance_matrix[current_node][candidate]
            score = regret * 0.5 + savings * 0.5

        if score > best_score:
            best_score = score
            best_node = candidate

    return best_node if best_node is not None else unvisited_nodes[0]
