def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    if current_node == depot:
        # Regret-weighted farthest: prefer nodes far from depot and close to current (depot)
        best = None
        best_score = -1.0
        for u in unvisited_nodes:
            dist_to_depot = distance_matrix[depot][u]
            # find nearest other unvisited node for regret
            other_dists = [distance_matrix[u][v] for v in unvisited_nodes if v != u]
            nearest_other = min(other_dists) if other_dists else dist_to_depot
            regret = dist_to_depot - nearest_other
            score = dist_to_depot + regret
            if score > best_score:
                best_score = score
                best = u
        return best

    # Default: regret-weighted nearest from current node
    # Compute ratio: distance from depot / (distance from current + epsilon)
    candidates = []
    for u in unvisited_nodes:
        dist_cur = distance_matrix[current_node][u]
        dist_dep = distance_matrix[depot][u]
        if dist_cur == 0:
            weight = 1e9
        else:
            weight = dist_dep / dist_cur
        candidates.append((weight, u))
    # pick node with highest weight (i.e., far from depot but close to current)
    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1]
