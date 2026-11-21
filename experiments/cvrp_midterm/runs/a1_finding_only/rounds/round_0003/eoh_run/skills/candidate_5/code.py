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

    # Component 1: proximity to current node (smaller is better -> invert).
    span_cur = float(np.max(d_cur) - np.min(d_cur)) if d_cur.size > 1 else 0.0
    prox = 1.0 - (d_cur - np.min(d_cur)) / (span_cur + 1e-12)

    # Component 2: depot-return saving (larger is better).
    saving = d_dep - d_cur
    span_sav = float(np.max(saving) - np.min(saving)) if saving.size > 1 else 0.0
    sav_n = (saving - np.min(saving)) / (span_sav + 1e-12)

    # Component 3: capacity fill ratio (larger is better).
    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) + 1e-12
    fill = np.clip(dem / cap, 0.0, 1.0)

    # Additive blend with tuned weights.
    score = 0.45 * prox + 0.35 * sav_n + 0.20 * fill

    # Tie-break: prefer larger residual capacity after serving (less waste).
    residual = (cap - dem) / cap
    score = score - 1e-6 * residual

    idx = int(np.argmax(score))
    return int(unvisited_nodes[idx])