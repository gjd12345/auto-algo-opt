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

    eps = 1e-9
    max_cur = float(np.max(d_cur)) if d_cur.size > 0 else 1.0
    max_dep = float(np.max(d_dep)) if d_dep.size > 0 else 1.0
    cap = float(rest_capacity) if rest_capacity > eps else eps

    f_dist = (d_cur + eps) / (max_cur + eps)
    f_dep = (d_dep + eps) / (max_dep + eps)
    f_dem = np.clip(dem / cap, 0.0, 1.0)

    # Weighted geometric mean: balance compactness, depot return, and demand fill
    w_dist, w_dep, w_dem = 0.55, 0.25, 0.20
    score = np.power(f_dist + eps, w_dist) \
          * np.power(f_dep + eps, w_dep) \
          * np.power(1.0 - 0.5 * f_dem + eps, w_dem)

    # Diversify: among near-tied top candidates pick the one with largest demand
    best_val = float(np.min(score))
    span = float(np.max(score) - best_val)
    band = 1e-3 * (span + 1.0)
    mask = score <= (best_val + band)
    if mask.sum() > 1:
        candidates = np.where(mask)[0]
        pick = candidates[np.argmax(dem[candidates])]
        return int(nodes[pick])

    return int(nodes[np.argmin(score)])