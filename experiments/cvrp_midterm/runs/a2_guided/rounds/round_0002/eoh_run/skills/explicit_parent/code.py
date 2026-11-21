def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(np.float64)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(np.float64)
    dem = demands[unvisited_nodes].astype(np.float64)

    # Span-proportional scale: mean distance from depot to unvisited customers.
    # This is scale-equivariant, so the score is invariant to coordinate scale.
    scale = float(np.mean(d_dep))
    if not np.isfinite(scale) or scale <= 0.0:
        scale = 1.0

    cap = float(rest_capacity)
    if cap <= 0.0:
        cap = 1.0

    # Normalized distance-to-current: dominant term, preserving greedy NN behaviour.
    s_cur = d_cur / scale
    # Normalized distance-to-depot: mild pull back toward depot proximity.
    s_dep = d_dep / scale
    # Capacity-pressure term: reward filling the vehicle (larger demand relative
    # to remaining capacity -> better). Bounded in [0, 1].
    fill = np.clip(dem / cap, 0.0, 1.0)
    s_cap = 1.0 - fill  # lower is better when demand closer to capacity

    # Combine with readable weights: current distance dominates, depot mild,
    # capacity pressure mild. All terms are dimensionless (scale-invariant).
    score = 1.0 * s_cur + 0.30 * s_dep + 0.20 * s_cap

    return int(unvisited_nodes[int(np.argmin(score))])