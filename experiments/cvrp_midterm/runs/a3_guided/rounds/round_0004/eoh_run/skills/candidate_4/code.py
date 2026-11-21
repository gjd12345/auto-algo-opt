def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    cur = distance_matrix[current_node][unvisited_nodes]
    to_depot = distance_matrix[unvisited_nodes, depot]
    stem = distance_matrix[current_node, depot]

    # Marginal detour of inserting c before the return leg (>= 0 by triangle ineq).
    detour = cur + to_depot - stem

    # Dimensionless demand pressure: defer heavy stops when capacity is tight.
    demand_frac = demands[unvisited_nodes] / (rest_capacity + 1e-12)

    # Scale-free normalized cost: detour per unit return distance, penalized
    # by how much of the remaining capacity this stop would consume.
    cost = detour / (to_depot + 1e-12) + demand_frac
    return int(unvisited_nodes[np.argmin(cost)])