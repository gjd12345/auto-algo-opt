def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(np.float64)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(np.float64)
    dem = demands[unvisited_nodes].astype(np.float64)

    # Span-proportional scale (no absolute length added). Invariant to coordinate scale.
    span = float(np.max(d_dep) - np.min(d_dep)) if unvisited_nodes.size > 1 else 0.0
    if not np.isfinite(span) or span <= 0.0:
        span = float(np.mean(d_dep))
    if not np.isfinite(span) or span <= 0.0:
        span = 1.0

    cap = float(rest_capacity)
    if cap <= 0.0:
        cap = 1.0

    d_cd = float(distance_matrix[current_node][depot])

    # Dimensionless quantities.
    saving = d_dep + d_cd - d_cur          # >= 0 typically
    proximity = d_cur + 1e-12              # avoid div-by-zero

    # Ratio priority: maximize (saving / proximity). Different functional form
    # from additive Clarke-Wright. Scale-invariant since ratio is dimensionless.
    ratio = saving / proximity

    # Fill reward: prefer using capacity now.
    fill = np.clip(dem / cap, 0.0, 1.0)

    # New parameter: alpha = 0.45 (was 0.20 additive fill weight).
    score = -(ratio) - 0.45 * fill

    # Secondary ordering stage: among near-ties (within a span-proportional
    # window) prefer closer to depot, then smaller proximity.
    window = 0.02 * max(ratio.max() - ratio.min(), 1e-12) if unvisited_nodes.size > 1 else 0.0
    primary = -(ratio) - 0.45 * fill
    best = float(np.min(primary))
    near = np.where(primary <= best + window)[0]
    if near.size > 1:
        # secondary: smaller depot distance, then smaller proximity
        sub = d_dep[near] / span + 1e-6 * (proximity[near] / span)
        pick = near[int(np.argmin(sub))]
    else:
        pick = int(np.argmin(primary))

    return int(unvisited_nodes[pick])