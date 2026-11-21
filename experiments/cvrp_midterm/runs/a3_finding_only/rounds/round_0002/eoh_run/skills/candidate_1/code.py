def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    # scale reference: farthest candidate from current node (span-proportional)
    span = float(np.max(d_cur))
    if span <= 0.0:
        return int(unvisited_nodes[0])
    # normalized immediate travel cost
    travel = d_cur / span
    # savings of serving this node directly vs. going via depot
    saving = (d_cur + d_dep - distance_matrix[current_node][depot]) / span
    # capacity fill ratio after serving this node (higher = better packing)
    node_demands = demands[unvisited_nodes]
    if rest_capacity > 0.0:
        fill = (rest_capacity - node_demands) / rest_capacity
    else:
        fill = np.zeros_like(d_cur)
    # scale-invariant priority: prefer short travel, high saving, high fill
    score = travel - 0.5 * saving - 0.5 * fill
    return int(unvisited_nodes[np.argmin(score)])