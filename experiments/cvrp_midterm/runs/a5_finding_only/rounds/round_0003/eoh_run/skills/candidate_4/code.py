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
    if len(unvisited_nodes) == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_to_depot = distance_matrix[unvisited_nodes, depot].astype(float)
    dem = demands[unvisited_nodes].astype(float)

    cap = float(rest_capacity) + 1e-9
    cap_scale = cap if cap > 1e-6 else 1.0

    # Lookahead: insertion cost now + best possible return cost afterwards.
    # After serving candidate i, remaining = cap - dem[i]; the return cost is
    # approximated by the depot distance from i (tour continues then returns).
    insertion = d_cur + d_to_depot

    # Load-aware urgency: when remaining capacity is tight relative to the
    # average demand, prefer candidates that use capacity efficiently.
    total_dem = float(np.sum(dem)) if len(dem) > 0 else 0.0
    mean_dem = total_dem / max(len(dem), 1)
    if mean_dem > 1e-9:
        fill_ratio = dem / mean_dem
    else:
        fill_ratio = np.ones_like(dem)
    tightness = max(0.0, 1.0 - cap_scale / max(total_dem, 1e-9))

    # Scale-invariant proximity term.
    mean_ins = float(np.mean(insertion)) if len(insertion) > 0 else 1.0
    if mean_ins <= 1e-12:
        mean_ins = 1.0
    ins_norm = insertion / mean_ins

    # Reward candidates whose depot distance is small relative to their
    # insertion cost (i.e. cheap to close the loop) and pack well when tight.
    loop_balance = d_to_depot / (insertion + 1e-12)

    score = ins_norm + 0.35 * loop_balance - (0.25 + 0.35 * tightness) * fill_ratio

    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])