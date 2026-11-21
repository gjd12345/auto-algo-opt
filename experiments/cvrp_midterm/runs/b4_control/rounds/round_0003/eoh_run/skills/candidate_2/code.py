def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    cap = float(rest_capacity)
    if cap <= 0.0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    # Capacity pressure: how tight the remaining capacity becomes after serving.
    load_after = (cap - dem) / cap  # in (0, 1], smaller = tighter
    pressure = 1.0 - load_after     # in [0, 1), larger = tighter

    # Returnability: far customers are expensive to abandon late.
    return_cost = dem * d_dep / cap

    # Score: greedy distance, penalized by capacity pressure scaled by depot
    # distance, encouraging serving far customers before capacity tightens.
    score = d_cur + 3.0 * pressure * d_dep + 0.5 * return_cost
    return int(unvisited_nodes[np.argmin(score)])