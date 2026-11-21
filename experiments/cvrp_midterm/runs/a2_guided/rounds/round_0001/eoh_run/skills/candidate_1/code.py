def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return 0
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    # savings: how much we gain by going current->node directly vs via depot
    savings = d_cur + d_dep - distance_matrix[depot][current_node]
    dem = demands[unvisited_nodes].astype(float)
    # primary score: prefer small distance, small depot detour, and high demand efficiency
    d_cur_safe = d_cur + 1e-9
    score = d_cur - savings * (dem / (rest_capacity + 1e-9))
    # secondary tie-break: closer to depot first among near-equal scores
    order = np.argsort(score, kind="stable")
    best_i = order[0]
    # cheap two-stage: among candidates within small relative tolerance of best, pick nearest to current
    best_score = score[best_i]
    tol = 1e-6 * (abs(best_score) + 1e-9)
    close = np.where(score <= best_score + tol)[0]
    if close.size > 1:
        best_i = close[np.argmin(d_cur[close])]
    return int(unvisited_nodes[best_i])