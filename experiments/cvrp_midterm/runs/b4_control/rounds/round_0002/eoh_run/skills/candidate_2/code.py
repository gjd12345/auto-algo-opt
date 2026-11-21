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
    dem = demands[unvisited_nodes].astype(float)

    # Clarke-Wright savings: going cur -> j instead of cur -> depot -> j
    savings = d_cur + d_dep - distance_matrix[current_node][depot]

    # Capacity pressure: normalized remaining load after servicing j
    load_frac = (cap - dem) / cap

    # Prefer high savings and low capacity pressure; mildly reward fuller loads
    score = savings - 0.6 * cap * (1.0 - load_frac) - 0.25 * d_dep * load_frac
    return int(unvisited_nodes[np.argmax(score)])