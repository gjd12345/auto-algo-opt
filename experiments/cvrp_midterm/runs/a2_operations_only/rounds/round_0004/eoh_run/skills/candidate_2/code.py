def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    savings = d_dep - d_cur
    # capacity-pressure term: prefer filling the vehicle's remaining capacity
    cap_denom = rest_capacity if rest_capacity > 1e-9 else 1e-9
    fill = demands[unvisited_nodes] / cap_denom  # larger => better utilization
    score = savings + fill
    # secondary ordering: among near-tied primary scores, take the closest node
    best = np.max(score)
    tol = 1e-6 * (abs(best) + 1.0)
    near = np.where(score >= best - tol)[0]
    if near.size > 1:
        return unvisited_nodes[near[np.argmin(d_cur[near])]]
    return unvisited_nodes[np.argmax(score)]