def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    current_node = int(current_node)
    depot = int(depot)
    unvisited_nodes = np.asarray(unvisited_nodes, dtype=int)
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_depot = distance_matrix[depot][unvisited_nodes].astype(float)
    dem = demands[unvisited_nodes].astype(float)

    cap = float(rest_capacity)
    fill = dem / cap if cap > 0.0 else np.zeros_like(dem)

    # Margin-based priority: reward customers whose depot distance exceeds the
    # detour cost, scaled by how well they fill the vehicle. This is a
    # ratio/dominance construction rather than an additive weighted sum.
    detour = d_cur + d_depot
    margin = d_depot * (0.5 + fill) - 0.5 * detour

    # Lexicographic tie-break: among high-margin candidates prefer nearest.
    best_margin = float(np.max(margin))
    tol = 0.35 * max(1.0, abs(best_margin))
    near_best = np.where(margin >= best_margin - tol)[0]
    if near_best.size == 0:
        return int(unvisited_nodes[int(np.argmax(margin))])

    choice = near_best[int(np.argmin(d_cur[near_best]))]
    return int(unvisited_nodes[int(choice)])