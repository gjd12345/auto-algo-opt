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
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_cur_dep = distance_matrix[current_node][depot]

    if current_node == depot:
        # Start with a near but demand-friendly customer: distance minus a mild
        # demand bonus normalized by remaining capacity.
        demands_unvisited = demands[unvisited_nodes]
        max_d = float(np.max(demands_unvisited)) if demands_unvisited.size else 1.0
        if max_d > 0:
            score = d_cur - 0.15 * d_cur_dep * (demands_unvisited / max_d)
        else:
            score = d_cur
        return int(unvisited_nodes[np.argmin(score)])

    savings = d_cur_dep + d_dep - d_cur

    demands_unvisited = demands[unvisited_nodes]
    max_d = float(np.max(demands_unvisited)) if demands_unvisited.size else 1.0
    cap_ratio = rest_capacity / max(1e-9, max_d)

    # Blend an explicit distance penalty into savings so route closure and
    # short extensions are jointly considered.
    score = savings - 0.25 * d_cur

    if cap_ratio < 2.5 and max_d > 0:
        # Stronger high-demand bias when capacity is tight.
        tightness = max(0.0, 1.0 - cap_ratio / 2.5)
        score = score + (0.02 + 0.08 * tightness) * (demands_unvisited / max_d)

    return int(unvisited_nodes[np.argmax(score)])