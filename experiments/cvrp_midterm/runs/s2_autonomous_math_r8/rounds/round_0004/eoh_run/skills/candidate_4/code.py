def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return 0

    nodes = np.asarray(unvisited_nodes)
    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    dem = demands[nodes].astype(float)

    scale = float(np.mean(d_dep) + np.mean(d_cur) + 1e-12)
    cap = rest_capacity if rest_capacity > 1e-12 else 1e-12

    # ---- Depot start: discrete polar-sector seed selection ----
    if current_node == depot:
        total_dem = float(np.sum(dem))
        rem_routes = total_dem / cap
        if rem_routes > 7.0:
            # outside-in: pick the farthest node in the farthest angular sector,
            # tie-broken by heaviest demand (largest load cleared per route)
            sector = np.floor(np.arctan2(
                distance_matrix[depot][nodes] * 0.0,  # placeholder keeps shape
                np.ones_like(d_cur)) * 0.0)  # trivial; use pure distance
            key = -(d_dep / scale) - 0.25 * (dem / cap)
        else:
            # compact radial-load seed: nearest feasible node, tie-broken by load fit
            key = (d_dep / scale) - 0.30 * (dem / cap)
        return int(nodes[int(np.argmin(key))])

    # ---- Polar geometry relative to the current depot-ray ----
    d0c = float(distance_matrix[depot][current_node])
    if not np.isfinite(d0c) or d0c < 0.0:
        d0c = 0.0

    # cos(theta_0) between depot->current ray and depot->candidate ray
    denom_cos = np.maximum(2.0 * d_dep * d0c, 1e-12)
    cos_t = np.clip((d_dep * d_dep + d0c * d0c - d_cur * d_cur) / denom_cos, -1.0, 1.0)

    # rho = elongation of the current->candidate leg vs depot rays
    rho = d_cur / np.maximum(d_dep + d0c, 1e-12)

    # ---- Capacity-adaptive voluntary early return (steeper slope) ----
    mean_dem = float(np.mean(dem))
    tau = 0.24 + 0.50 * min(1.0, mean_dem / cap)

    # If current ray is far off the depot-ray and capacity is thin, go home
    if d0c > 0.0:
        radial_align = (d_dep * cos_t) / np.maximum(d_dep, 1e-12)  # = cos_t here
    # Use best candidate's residual slack for the gate
    slack = cap - dem  # remaining capacity after serving each candidate
    best_idx = int(np.argmin(d_cur - 0.75 * d_dep))
    rho_best = float(rho[best_idx])
    if rho_best < tau and float(np.min(slack)) < 0.5 * cap:
        # return only if heading back is competitive with best forward leg
        if d_cur[best_idx] >= d_dep[best_idx] * (1.0 - tau) * 1.15:
            return int(depot)

    # ---- Lexicographic sweep: fix angular band, then rank by slack + radius ----
    # Angular band: candidates within ~45deg of the current depot-ray direction
    band = cos_t >= 0.70
    if not np.any(band):
        band = np.ones_like(cos_t, dtype=bool)

    # Primary: within band, prefer low elongation (stay on the petal)
    # Secondary: prefer candidates that leave healthier residual slack
    # Tertiary: slight radial pull
    ang_rank = np.where(band, rho, rho + 1.0)  # penalty for outside band
    slack_rank = -slack / cap                   # more slack -> more negative
    radial_rank = (d_cur - 0.75 * d_dep) / scale

    key = ang_rank + 0.35 * slack_rank + 0.25 * radial_rank

    return int(nodes[int(np.argmin(key))])