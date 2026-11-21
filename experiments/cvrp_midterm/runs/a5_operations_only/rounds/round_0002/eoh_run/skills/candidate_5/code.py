def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
    dem = demands[unvisited_nodes].astype(float)
    cap = rest_capacity if rest_capacity > 0 else 1.0

    # headroom after serving this node, normalized to (0,1]
    headroom = np.maximum(cap - dem, 0.0) / cap + 1e-6

    # squared distance penalized by tight headroom -> prefer near nodes that
    # also leave useful slack; multiplicative form keeps scale invariance
    urg = (d_cur * d_cur) / headroom

    best = urg.min()
    tol = 1e-6 * (abs(best) + 1.0)
    ties = np.where(urg <= best + tol)[0]

    if ties.size > 1:
        cand = unvisited_nodes[ties]
        return int(cand[np.argmin(d_dep[ties])])

    return int(unvisited_nodes[int(np.argmin(urg))])