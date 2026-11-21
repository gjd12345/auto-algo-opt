def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    cur = distance_matrix[current_node][unvisited_nodes]
    to_depot = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)
    # Primary score: one term replaced -> radial savings form for depot distance
    score = cur + (2.0 * distance_matrix[current_node][depot] - to_depot) + 0.001 * rest_capacity
    order = np.argsort(score)
    best = order[0]
    # Cheap second ordering stage: among near-ties, prefer larger demand / distance
    best_score = score[best]
    tol = 1e-9 + 1e-6 * abs(best_score)
    near = order[score[order] <= best_score + tol]
    if near.size > 1:
        ratios = dem[near] / (cur[near] + 1e-12)
        best = near[np.argmax(ratios)]
    return int(unvisited_nodes[best])