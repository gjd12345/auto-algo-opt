def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot
    cur = distance_matrix[current_node][unvisited_nodes]
    to_depot = distance_matrix[unvisited_nodes, depot]
    stem = distance_matrix[current_node, depot]
    # Savings from inserting the node before returning, relative to replaced leg.
    savings = stem + to_depot - cur
    # Span-proportional normaliser (max depot distance among candidates), scale-free.
    span = float(np.max(to_depot)) if to_depot.size > 0 else 1.0
    span = span if span > 1e-12 else 1.0
    score = savings / span
    # Cheap second-order stage: prefer higher demand saturation on near ties.
    order = np.argsort(-score)
    best = order[0]
    best_score = score[best]
    tol = 1e-9
    # Among candidates within tol of the best score, break ties by demand ratio.
    tied = order[score[order] >= best_score - tol]
    if tied.size > 1:
        cap = rest_capacity if rest_capacity > 1e-12 else 1.0
        dem_ratio = demands[unvisited_nodes[tied]] / cap
        best = tied[int(np.argmax(dem_ratio))]
    return int(unvisited_nodes[best])