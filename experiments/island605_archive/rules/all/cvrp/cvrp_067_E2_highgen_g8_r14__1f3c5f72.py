def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Seed route with farthest customer
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    # For each unvisited customer, compute a score combining:
    # - distance from current node (want small)
    # - angular deviation from the direction from depot to current node (want small)
    # Use a weighted sum: w1 * dist + w2 * angle_diff
    w1, w2 = 0.6, 0.4

    # Direction vector from depot to current node
    dx_cur = distance_matrix[current_node]  # dummy, we need actual coordinates – use distances as proxy
    # Instead, use polar angle proxy via atan2 of distances from depot
    # Simple proxy: angle = atan2(y, x) not available, so use normalized distance differences

    best_node = None
    best_score = float('inf')

    for u in unvisited_nodes:
        dist = distance_matrix[current_node][u]
        # Angular deviation proxy: |distance from depot to u - distance from depot to current_node|
        angle_dev = abs(distance_matrix[depot][u] - distance_matrix[depot][current_node])
        score = w1 * dist + w2 * angle_dev
        if score < best_score:
            best_score = score
            best_node = u

    # Early return condition: if best node is far both from current and depot, return
    if best_node is not None:
        best_dist = distance_matrix[current_node][best_node]
        best_depot_dist = distance_matrix[depot][best_node]
        current_depot_dist = distance_matrix[depot][current_node]
        if best_depot_dist > current_depot_dist and best_dist > 0.6 * current_depot_dist:
            return depot

    return best_node if best_node is not None else depot
