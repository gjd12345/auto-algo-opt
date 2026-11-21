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

    eps = 1e-9
    nodes = np.asarray(unvisited_nodes)

    d_cur = distance_matrix[current_node][nodes].astype(np.float64)
    d_dep = distance_matrix[depot][nodes].astype(np.float64)
    dem = demands[nodes].astype(np.float64)

    d_cur_scale = float(np.mean(d_cur)) + eps
    d_dep_scale = float(np.mean(d_dep)) + eps

    # Pull toward current node, push toward depot-adjacent detour savings
    proximity = 1.0 / (d_cur / d_cur_scale + eps)

    # Normalized radial position (near depot -> small, far -> large)
    radial = d_dep / d_dep_scale

    # Capacity-fit: prefer demands that pack well into remaining capacity
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    fill = np.clip(dem / cap, 0.0, 1.0)
    fit = 1.0 + fill

    # Preferred direction: far customers that also save a big depot detour
    # detour_save ~ 1 when d_dep >> d_cur (good stop on the way out)
    detour_save = 1.0 + (d_dep - d_cur) / (d_dep + d_cur + eps)

    score = proximity * fit * detour_save * (0.5 + 0.5 * radial)

    best = int(np.argmax(score))
    best_score = float(score[best])

    # Early depot return: if even the best continuation is a poor fit,
    # go home. Threshold ties the decision to current position.
    d_home = float(distance_matrix[current_node][depot])
    if best_score < 0.05 * (d_home + 1.0):
        return depot

    return int(nodes[best])