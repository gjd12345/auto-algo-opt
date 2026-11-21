def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    cap = float(rest_capacity)
    if cap <= 0.0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
    d_cd = float(distance_matrix[current_node][depot]) + 1e-9
    dem = demands[unvisited_nodes].astype(float)

    # Savings-style term: how much is gained by inserting the customer
    # between the current node and the depot.
    savings = d_cd + d_dep - d_cur
    savings_norm = savings / (d_cd + d_dep + 1e-9)

    # Radial alignment: prefer customers roughly in the direction the
    # vehicle is already heading (away from depot), so clusters stay compact.
    outward = d_dep / (d_dep + d_cur + 1e-9)

    # Capacity pressure: fill the vehicle efficiently when nearly full.
    fill = cap / max(cap + dem.max() if dem.size else cap, 1e-9)
    demand_term = (dem / max(cap, 1e-9)) * (1.0 - fill)

    score = -savings_norm - 0.25 * outward + 0.5 * demand_term
    return int(unvisited_nodes[np.argmin(score)])