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
        return 0

    nodes = np.asarray(unvisited_nodes)
    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    d_cur_dep = float(distance_matrix[current_node][depot])

    dem = demands[nodes].astype(float)
    cap = float(rest_capacity) if rest_capacity > 0 else 1e-9

    # Detour cost of inserting each node before returning to depot:
    #   (cur -> node) + (node -> depot) - (cur -> depot)
    detour = d_cur + d_dep - d_cur_dep

    # Saving relative to just going straight back to the depot.
    # Nodes close to the current->depot corridor produce small detour.
    saving = d_cur_dep - detour  # = d_cur_dep - (d_cur + d_dep - d_cur_dep)

    # Fill ratio: how full the vehicle would be after serving each node
    fill_after = (dem / cap)
    # Penalize nodes that leave little room (encourage balanced usage)
    tightness = 1.0 + 0.8 * np.clip(fill_after - 0.5, 0.0, 1.0)

    # Primary score: minimize detour per unit of "forward progress"
    # Blend: prefer small detour, prefer small fill_after penalty
    score = detour * tightness - 0.15 * saving

    # Tiny secondary tiebreak: closer to current node preferred
    score = score + 1e-6 * d_cur

    return int(nodes[int(np.argmin(score))])