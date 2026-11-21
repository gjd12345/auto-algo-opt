def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if len(unvisited_nodes) == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)

    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) + 1e-9
    load_frac = dem / cap

    # savings-like term: how much cheaper is depot->c over current->c
    savings = d_dep - d_cur

    # slack: prefer filling the vehicle well (1 means it just fits)
    slack = load_frac

    # combined discounted distance: candidates that save more and fit better win
    score = d_cur - 0.5 * savings + 0.8 * d_cur * (1.0 - slack)

    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])