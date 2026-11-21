def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return 0

    nodes = np.asarray(unvisited_nodes)
    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    d_depot_cur = float(distance_matrix[depot][current_node])
    dem = demands[nodes].astype(float)

    # Capacity fill urgency: prefer demands that nearly fill the remaining capacity.
    safe_rest = max(float(rest_capacity), 1e-9)
    fill = dem / safe_rest
    fill_pen = np.abs(1.0 - fill)

    # Radial deviation proxy: how far the candidate lies "outward" relative
    # to the current position along the depot->current radial line.
    # Using distance geometry: compare candidate depth from depot vs current depth.
    # A candidate aligned outward keeps depth increasing; penalize backtracking inward.
    inward = np.maximum(0.0, d_depot_cur - d_dep)

    # Sweep/angular proxy without coordinates: use triangle-inequality-derived
    # angular surrogate = (d_cur^2 + d_depot_cur^2 - d_dep^2) / (2*d_cur*d_depot_cur+eps)
    # Larger value => more aligned with current radial direction (keeps route smooth).
    denom = 2.0 * np.maximum(d_cur, 1e-9) * max(d_depot_cur, 1e-9) + 1e-9
    align = (d_cur * d_cur + d_depot_cur * d_depot_cur - d_dep * d_dep) / denom

    # Composite score: reward alignment, penalize distance, penalize inward drift,
    # and penalize leaving a big capacity gap (encourage fuller loads).
    score = (
        d_cur
        - 0.35 * d_dep
        + 1.5 * inward
        - 0.5 * align
        + 0.25 * fill_pen
    )

    # Small deterministic tie-break toward larger demand to fill vehicles.
    score = score - 1e-6 * dem

    return int(nodes[int(np.argmin(score))])