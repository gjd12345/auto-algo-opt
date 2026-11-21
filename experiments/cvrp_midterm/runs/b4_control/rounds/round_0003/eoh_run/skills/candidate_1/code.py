def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    cap = float(rest_capacity)
    if cap <= 0.0:
        return depot

    # Savings-style: prefer customers that save more by being inserted
    # between depot and current node relative to returning to depot.
    savings = d_dep + d_cur - distance_matrix[depot][unvisited_nodes]

    # Normalize demand pressure.
    demand_ratio = dem / cap

    # New parameterization: strong savings weight, moderate demand penalty,
    # mild preference for farther-from-depot customers.
    score = -1.2 * savings + 0.8 * d_cur + 0.5 * d_dep + 1.5 * demand_ratio * d_cur
    return int(unvisited_nodes[np.argmin(score)])