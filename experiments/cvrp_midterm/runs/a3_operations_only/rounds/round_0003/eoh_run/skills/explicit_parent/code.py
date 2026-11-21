def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    unvisited = np.asarray(unvisited_nodes, dtype=np.int64)
    if unvisited.size == 0:
        return 0

    d_cur = distance_matrix[current_node][unvisited]
    d_dep = distance_matrix[depot][unvisited]
    dem = demands[unvisited]

    cap = max(rest_capacity, 1e-9)
    # Stronger pull toward far customers when the truck is mostly empty:
    # an "urgency" factor that decays as the remaining capacity shrinks.
    urgency = np.sqrt(cap / max(cap, 1e-9) + (d_dep / (np.min(d_dep) + 1e-9)))

    # Savings-style score: reward customers far from the depot relative to
    # their distance from the current position (Clarke-Wright flavour),
    # discounted by an urgency term and by demand size.
    savings = (d_dep - d_cur) / (d_dep + 1e-9)
    scores = -savings * urgency * (1.0 + dem / (cap + 1e-9))

    order = np.argsort(scores)
    best = order[0]
    # Second ordering stage: among candidates whose primary score is within
    # a small band of the best, prefer the one with the smallest d_cur.
    cutoff = scores[best] + 0.02 * (np.abs(scores[best]) + 1.0)
    close = unvisited[scores <= cutoff]
    if close.size > 1:
        close_d = distance_matrix[current_node][close]
        return int(close[np.argmin(close_d)])
    return int(unvisited[best])