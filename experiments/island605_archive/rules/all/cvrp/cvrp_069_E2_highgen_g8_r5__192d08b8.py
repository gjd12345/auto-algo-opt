def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    # Compute insertion cost if visited now vs. if visited later (from depot)
    cost_now = distance_matrix[current_node][unvisited_nodes]
    cost_later = distance_matrix[depot][unvisited_nodes]

    # Regret = extra cost if delayed (larger regret = more urgent to visit now)
    regret = cost_later - cost_now

    # Weight by capacity pressure: high pressure (low rest_capacity) favors local moves
    max_demand = max(demands[unvisited_nodes]) if len(unvisited_nodes) > 0 else 1
    capacity_pressure = 1.0 - (rest_capacity / (rest_capacity + max_demand))

    # Combine: maximize regret * (1 - pressure) for early route,
    # but fallback to nearest when capacity is tight
    if capacity_pressure < 0.5:
        # Early/mid route: favor high regret (urgent to visit now)
        scores = -regret  # negate because argmin
        best_idx = np.argmin(scores)
    else:
        # Late route: nearest neighbor to avoid wasted travel
        scores = cost_now
        best_idx = np.argmin(scores)

    # Safety: ensure best_idx is within bounds
    if best_idx >= len(unvisited_nodes):
        return depot
    return unvisited_nodes[best_idx]
