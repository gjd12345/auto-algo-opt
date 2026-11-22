def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        # Start new route: choose farthest customer from depot
        distances_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(distances_from_depot)]

    # For non-depot, compute regret-based score for each candidate
    best_node = None
    best_score = -np.inf

    for u in unvisited_nodes:
        # Cost of inserting u now: distance from current_node to u
        cost_now = distance_matrix[current_node][u]
        # Cost of inserting u later: estimate as min distance from u to any other unvisited node
        other_nodes = unvisited_nodes[unvisited_nodes != u]
        if len(other_nodes) > 0:
            cost_later = np.min(distance_matrix[u][other_nodes])
        else:
            cost_later = distance_matrix[u][depot]  # fallback to depot
        # Regret: how much extra cost if we delay visiting u
        regret = cost_later - cost_now
        # Penalty for being far from depot (to avoid premature returns)
        depot_penalty = 0.3 * distance_matrix[depot][u] / (distance_matrix[current_node][u] + 1e-10)
        score = regret + depot_penalty

        if score > best_score:
            best_score = score
            best_node = u

    if best_node is None:
        return depot
    return best_node
