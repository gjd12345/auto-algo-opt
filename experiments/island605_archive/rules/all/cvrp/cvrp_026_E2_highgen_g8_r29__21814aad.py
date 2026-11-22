def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    if current_node == depot:
        # Seed the route with the customer that has the largest regret:
        # difference between farthest and second farthest from depot
        dists = distance_matrix[depot][unvisited_nodes]
        if len(dists) < 2:
            return unvisited_nodes[0]
        sorted_indices = np.argsort(dists)
        best = dists[sorted_indices[-1]]
        second_best = dists[sorted_indices[-2]]
        regret = best - second_best
        best_idx = sorted_indices[-1]
        return unvisited_nodes[best_idx]

    # Compute regret-like score for each unvisited customer
    scores = []
    for u in unvisited_nodes:
        # Cost if we visit u now
        current_cost = distance_matrix[current_node][u]
        # Cost if we skip u and go to depot first (simulate worst-case postponement)
        skip_cost = distance_matrix[current_node][depot] + distance_matrix[depot][u]
        regret = skip_cost - current_cost
        # Also consider capacity: prefer customers that use more capacity early
        capacity_ratio = demands[u] / rest_capacity if rest_capacity > 0 else 0
        # Combine regret and capacity usage (higher is better)
        score = regret + capacity_ratio * 0.1
        scores.append(score)

    scores = np.array(scores)
    best_idx = np.argmax(scores)
    best_node = unvisited_nodes[best_idx]

    # Return to depot only if even the best candidate is worse than returning
    if distance_matrix[current_node][depot] < distance_matrix[current_node][best_node]:
        return depot
    return best_node
