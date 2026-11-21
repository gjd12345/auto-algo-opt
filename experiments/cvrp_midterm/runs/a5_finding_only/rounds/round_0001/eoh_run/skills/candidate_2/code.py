def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_cur_dep = distance_matrix[current_node][depot]

    # Savings: how much we save by inserting the customer now instead of
    # returning to depot then going out to it.
    savings = d_cur_dep + d_dep - d_cur

    # Radial coherence: prefer customers at similar depot distance to current
    # node (route stays compact), normalized by depot distance to keep it
    # scale-free relative to the savings term.
    denom = d_dep + 1e-9
    radial = -np.abs(d_dep - distance_matrix[current_node][depot]) / denom

    # Load utilization: prefer larger demands when capacity is tight,
    # encouraging fuller routes without depending on absolute scale.
    demand_ratio = demands[unvisited_nodes] / (rest_capacity + 1e-9)
    load_term = 0.5 * demand_ratio

    score = savings + 1.0 * radial + load_term
    return int(unvisited_nodes[np.argmax(score)])