def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    cap = max(rest_capacity, 1e-9)
    fill = dem / cap

    # Detour overhead: extra distance incurred vs. going straight back to depot.
    detour = d_cur + d_dep - distance_matrix[current_node][depot]

    # Reward customers whose demand fills the remaining capacity well (packing).
    # Use a concave transform via sqrt to penalize extreme small fills less.
    pack_bonus = np.sqrt(fill)

    # Radial preference: prefer customers farther from depot earlier (sweep-like),
    # but discounted by how cheap the detour is.
    radial = d_dep / (d_cur + 1e-9)

    # Composite multiplicative score: minimize detour, maximize fill and radial pull.
    scores = detour / (1.0 + pack_bonus) - 0.35 * radial

    return int(unvisited_nodes[np.argmin(scores)])