def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)

    cur_to_dep = float(distance_matrix[current_node][depot])

    mean_dcur = float(np.mean(d_cur))
    if mean_dcur <= 0:
        mean_dcur = 1.0
    near = d_cur / mean_dcur + 1e-9

    mean_ddep = float(np.mean(d_dep))
    if mean_ddep <= 0:
        mean_ddep = 1.0
    rad = d_dep / mean_ddep + 1e-9

    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) + 1e-9
    load_frac = dem / cap
    pack = 1.0 + load_frac

    # continuation via cosine of turn angle (scale-invariant)
    a = d_cur
    b = cur_to_dep + 1e-12
    c = d_dep
    denom = 2.0 * a * b + 1e-12
    cos_angle = np.clip((a * a + b * b - c * c) / denom, -1.0, 1.0)
    cont = 1.0 - cos_angle  # 0 = straight ahead, 2 = U-turn

    score = (near * near) / (pack * pack * (rad + 1e-6) * (1.0 + 0.3 * cont))
    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])