def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)

    # Local scale from both distance sets to keep score scale-homogeneous.
    span = float(np.max(d_cur) - np.min(d_cur)) if d_cur.size > 1 else 0.0
    span_d = float(np.max(d_dep) - np.min(d_dep)) if d_dep.size > 1 else 0.0
    scale = span + span_d + 1e-12

    # Saving-style term: prefer nodes that are close now but far from depot.
    saving = (d_dep - d_cur) / scale

    # Proximity term normalised similarly.
    prox = d_cur / scale

    # Capacity-aware: fraction of remaining capacity this customer fills.
    rc = float(rest_capacity) + 1e-12
    dem = demands[unvisited_nodes].astype(float)
    fill = dem / rc

    # Combine: reward savings, penalise distance, mildly reward fill.
    w_fill = 0.08 * (dem / (dem + 1e-12))  # value demand magnitudes
    score = -0.55 * saving + 0.75 * prox - w_fill * fill

    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])