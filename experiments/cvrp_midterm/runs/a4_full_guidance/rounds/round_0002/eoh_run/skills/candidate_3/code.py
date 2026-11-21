def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    eps = 1e-9
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    # Direction from current node to depot (as a vector proxy using distance geometry)
    # We use the law-of-cosines to get cos of angle at current node between
    # (current -> depot) and (current -> candidate).
    a = distance_matrix[current_node][depot]          # side current->depot
    b = d_cur                                          # side current->candidate
    c = d_dep                                          # side depot->candidate
    denom = 2.0 * a * b + eps
    cos_angle = (a * a + b * b - c * c) / denom

    # Angular alignment: larger cos => candidate direction from current node
    # points more back toward depot direction; blend with angular opening
    # (1 - cos) to reward "sweeping" candidates that fan out from the depot ray.
    # Capacity-fill factor: prefer filling remaining capacity well.
    cap_frac = dem / (rest_capacity + eps)

    # Primary score: angular term (1 - cos) gated by capacity fill and
    # mild proximity. Scale-free because cos is dimensionless.
    score = (1.0 - cos_angle) * (1.0 + cap_frac) / (b / (a + eps) + eps)

    s_min = np.min(score)
    s_max = np.max(score)
    span = s_max - s_min
    if span <= eps:
        return int(unvisited_nodes[np.argmin(d_cur)])
    tie_tol = 0.02 * span
    near = score >= (s_max - tie_tol)
    candidates = unvisited_nodes[near]
    if candidates.size == 0:
        candidates = unvisited_nodes
    best_idx = np.argmin(distance_matrix[current_node][candidates])
    return int(candidates[best_idx])