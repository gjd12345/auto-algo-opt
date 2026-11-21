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
    cur = current_node
    cand = unvisited_nodes
    d_cur = distance_matrix[cur][cand]
    d_dep = distance_matrix[depot][cand]
    d_cd = distance_matrix[cur][depot]
    dem = demands[cand]

    # Clarke-Wright saving of inserting candidate between current node and depot
    saving = d_cd + d_dep - d_cur

    # Fill ratio: how loaded the vehicle would be after taking this candidate
    cap = max(rest_capacity, 1e-9)
    fill = dem / cap  # in (0,1]
    fill = np.clip(fill, 0.0, 1.0)

    # Tightening factor: as we approach full load, prioritize savings more strongly
    # 1 at empty, growing as fill -> 1
    tighten = 1.0 + 2.0 * fill

    # Combined value: prioritize big savings when nearly full, near distance otherwise
    value = tighten * saving - d_cur

    best = int(np.argmax(value))

    # Tie-break: among near-equal values, pick nearest candidate
    vmax = value[best]
    tie_tol = 1e-9 * (abs(vmax) + 1.0)
    near = np.where(value >= vmax - tie_tol)[0]
    if near.size > 1:
        best = int(near[np.argmin(d_cur[near])])

    return int(cand[best])