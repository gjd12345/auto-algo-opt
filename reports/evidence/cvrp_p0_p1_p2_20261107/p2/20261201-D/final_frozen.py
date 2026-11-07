def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction.

    Args:
        current_node:    index of the current node (0 = depot)
        depot:           index of the depot (always 0)
        unvisited_nodes: array of feasible unvisited customer indices
                         (already filtered to satisfy remaining capacity)
        rest_capacity:   remaining vehicle capacity
        demands:         demand of every node (index 0 = depot demand = 0)
        distance_matrix: pairwise Euclidean distance matrix
    Returns:
        Index of the next node to visit, or 0 to return to the depot early.
    """
    unvisited_nodes = np.asarray(unvisited_nodes, dtype=np.int64)
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    if current_node == depot:
        # Deterministic nearest-neighbor start.
        return int(unvisited_nodes[np.argmin(d_dep)])

    d_cur_to = distance_matrix[current_node][unvisited_nodes]
    d_depot_to = distance_matrix[depot][unvisited_nodes]
    savings = distance_matrix[current_node][depot] + d_depot_to - d_cur_to

    # Capacity interaction: when capacity is tight, favor closing/returning
    # savings more strongly (radial preference toward depot).
    cap_ratio = 0.0
    total_cap = rest_capacity + float(np.sum(demands[unvisited_nodes]))
    if total_cap > 1e-12:
        cap_ratio = float(rest_capacity) / total_cap
    cap_ratio = max(0.0, min(1.0, cap_ratio))

    # Score: lower is better. Blend route-coherent increment with depot savings.
    # Tight capacity -> higher weight on savings (depot-aware radial preference).
    w_save = 0.35 + 0.45 * (1.0 - cap_ratio)
    w_cur = 1.0 - 0.5 * (1.0 - cap_ratio)

    score = w_cur * d_cur_to - w_save * savings

    return int(unvisited_nodes[np.argmin(score)])