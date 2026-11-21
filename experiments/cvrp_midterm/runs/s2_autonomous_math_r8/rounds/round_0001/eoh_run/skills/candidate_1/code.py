def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction.

    Args:
        current_node:    index of the current node (0 = depot)
        depot:           index of the depot (always 0)
        unvisited_nodes: array of feasible unvisited customer indices
                         (already filtered to satisfy remaining capacity)
        rest_capacity:   remaining vehicle capacity
        demands:         demand of every node (index 0 = depot demand = 0)
        distance_matrix: pairwise Euclidean distance matrix
    Returns:
        Index of the next node to visit, or 0 to return to the depot early.
    """
    if unvisited_nodes.size == 0:
        return 0

    nodes = np.asarray(unvisited_nodes)
    dem = demands[nodes].astype(float)

    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    d_cur_dep = distance_matrix[current_node][depot]

    # Global distance scale (scale-invariant: ratios only)
    all_d = distance_matrix[nodes][:, nodes].astype(float)
    scale = float(np.max(all_d)) if all_d.size > 0 else 1.0
    if scale <= 0.0:
        scale = 1.0

    rest = float(rest_capacity)
    if rest <= 0.0:
        rest = 1.0

    if current_node == depot:
        # Depot-start: scale-free outside-in / radial-load seed.
        # Prefer far customers weighted by relative demand (fill big loads early).
        rel_dem = dem / max(rest, 1e-12)          # dimensionless
        rel_dist = d_dep / scale                  # dimensionless
        score = -(rel_dist + 0.5 * rel_dem)       # maximize -> minimize negative
        return int(nodes[int(np.argmin(score))])

    # Mid-route: moderate depot pull + scale-free capacity-fill modulation.
    alpha_mid = 0.6
    rel_cur = d_cur / scale
    rel_dep = d_dep / scale

    # Capacity-fill: prefer candidates that leave a balanced residual.
    # fill_ratio in [0,1] both dimensionless; use closeness to 1 (good filling).
    fill = dem / max(rest, 1e-12)                 # dimensionless
    fill_term = -0.3 * np.minimum(fill, 1.0)      # reward filling capacity

    # Small tie-break: prefer larger demand among equals (scale-free).
    # Shift local relative distance by current-leg relative distance for balance.
    local = d_cur / (d_cur_dep + scale)           # dimensionless in (0,1)

    score = rel_cur - alpha_mid * rel_dep + fill_term + 1e-3 * local

    # Strict improvement vs pure nearest (never regress).
    nearest_idx = int(np.argmin(d_cur))
    best_idx = int(np.argmin(score))

    # If the heuristic pick is much closer (comparable), prefer nearest.
    if d_cur[best_idx] > d_cur[nearest_idx] * (1.0 + 1e-9):
        # Heuristic chose farther node only if fill deprioritizes it; ensure
        # nearest wins when scores are within a dimensionless tie band.
        span = float(np.max(score) - np.min(score))
        band = 1e-9 * (span + 1.0)
        if score[nearest_idx] <= float(np.min(score)) + band:
            return int(nodes[nearest_idx])

    return int(nodes[best_idx])