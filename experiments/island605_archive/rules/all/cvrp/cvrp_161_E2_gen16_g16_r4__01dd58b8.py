def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    feasible = [u for u in unvisited_nodes if demands[u] <= rest_capacity]
    if not feasible:
        return depot
    feasible = np.array(feasible)
    depot_dist = distance_matrix[depot][feasible]
    current_dist = distance_matrix[current_node][feasible]
    demand_ratio = demands[feasible] / rest_capacity
    regret = (depot_dist - current_dist) * (1 + 0.5 * demand_ratio)
    return feasible[np.argmax(regret)]
