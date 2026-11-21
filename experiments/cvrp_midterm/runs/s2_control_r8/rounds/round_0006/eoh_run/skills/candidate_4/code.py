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
    dem = demands[nodes].astype(float)

    # Detour saving: benefit of inserting node between current position and depot
    detour_saving = 2.0 * d_dep - d_cur

    # Capacity urgency: prefer customers whose demand strongly uses remaining capacity
    safe_rest = max(float(rest_capacity), 1e-9)
    cap_ratio = dem / safe_rest
    urgency = np.sqrt(np.clip(cap_ratio, 0.0, 1.0))

    # Consistency: reward nodes roughly in the same direction from the depot
    dcur_norm = np.maximum(d_cur, 1e-9)
    consistency = d_dep / dcur_norm

    score = detour_saving * (1.0 + urgency) + 0.1 * consistency

    # Prefer high score, with a small bias toward larger demand on ties
    combined = score + 1e-6 * dem
    return int(nodes[int(np.argmax(combined))])