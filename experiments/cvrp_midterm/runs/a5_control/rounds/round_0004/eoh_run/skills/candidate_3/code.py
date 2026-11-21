def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    current_node = int(current_node)
    depot = int(depot)
    unvisited_nodes = np.asarray(unvisited_nodes, dtype=int)

    if unvisited_nodes.size == 0:
        return depot

    cap = float(rest_capacity)
    if cap <= 0.0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_depot = distance_matrix[depot][unvisited_nodes].astype(float)
    demand = demands[unvisited_nodes].astype(float)

    eps = 1e-9
    # Normalized proximity: closer is better (in [0,1] roughly).
    dmax_cur = d_cur.max()
    prox = 1.0 - d_cur / (dmax_cur + eps) if dmax_cur > eps else np.ones_like(d_cur)

    # Urgency to serve far-from-depot customers: larger depot distance => higher.
    dmax_depot = d_depot.max()
    far = d_depot / (dmax_depot + eps) if dmax_depot > eps else np.zeros_like(d_depot)

    # Capacity utilization preference: prefer larger demand chunks when capacity tight.
    tightness = 1.0 - cap
    if tightness < 0.0:
        tightness = 0.0
    fill = demand / (cap + eps)

    # Multiplicative blend of proximity and urgency, weighted by fill.
    score = prox * (1.0 + 0.5 * far + 0.3 * fill + 0.4 * tightness * fill)

    return int(unvisited_nodes[np.argmax(score)])