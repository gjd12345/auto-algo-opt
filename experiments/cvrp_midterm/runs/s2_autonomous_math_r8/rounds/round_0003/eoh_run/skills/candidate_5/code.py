def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return 0

    nodes = np.asarray(unvisited_nodes)
    dem = demands[nodes].astype(float)

    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    d_cur_dep = float(distance_matrix[current_node][depot])

    rest = float(rest_capacity)
    if rest <= 0.0:
        rest = 1.0

    # Distance scale from unvisited submatrix (scale-free).
    d_all = distance_matrix[nodes][:, nodes].astype(float)
    scale = float(np.max(d_all)) if d_all.size > 0 else 1.0
    if scale <= 0.0:
        scale = 1.0

    if current_node == depot:
        # Depot start: compactness-first with mild demand pull.
        rel_dist = d_dep / scale
        rel_dem = dem / rest
        score = rel_dist - 0.45 * rel_dem
        return int(nodes[int(np.argmin(score))])

    # Dimensionless radial pull (linear) and elongation ratio.
    alpha = 0.82
    radial = (d_cur - alpha * d_dep) / scale

    axis = d_cur_dep + d_dep
    rho = d_cur / np.maximum(axis, 1e-12)

    # Compactness: relative savings of serving this node vs returning.
    compact = (d_cur_dep + d_dep - d_cur) / np.maximum(d_cur_dep + d_dep, 1e-12)

    # Fill fraction if this node is taken.
    fill = np.minimum(dem / rest, 1.0)

    # Multiplicative-in-spirit but additive standardized combination:
    # radial pressure, elongation, compactness reward, mild fill reward.
    beta = 0.11
    score = 0.60 * radial + 0.50 * rho - 0.35 * compact - beta * fill

    # Tie-break among near-best candidates by preferring larger fill.
    best_k = int(np.argmin(score))
    s_best = float(score[best_k])
    tol = 1e-9 * max(1.0, abs(s_best))
    near = np.where(score <= s_best + tol)[0]
    if near.size > 1:
        # prefer candidate with higher fill fraction (tighter packing)
        fills = fill[near]
        best_k = int(near[int(np.argmax(fills))])

    # Capacity-adaptive early-return gate: tighter as truck fills up.
    mean_dem = float(np.mean(dem)) if dem.size > 0 else 0.0
    load_frac = mean_dem / rest
    if load_frac > 1.0:
        load_frac = 1.0
    best_fill = float(fill[best_k])
    # rho threshold rises with load and with the best candidate's fill,
    # so near-full, high-elongation candidates trigger a return.
    tau = 0.50 + 0.18 * load_frac + 0.10 * best_fill
    if float(rho[best_k]) > tau:
        return 0

    return int(nodes[best_k])