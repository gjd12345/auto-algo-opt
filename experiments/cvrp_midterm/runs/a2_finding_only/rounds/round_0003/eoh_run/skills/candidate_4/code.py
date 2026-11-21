def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    dm = distance_matrix
    idx = unvisited_nodes

    span = float(np.max(dm))
    if not np.isfinite(span) or span <= 0.0:
        span = 1.0

    cap = float(rest_capacity)
    dem = demands[idx].astype(np.float64)

    d_cur = dm[current_node][idx] / span
    d_dep = dm[depot][idx] / span
    # Direct depot-current distance as the reference "return" leg.
    d_cur_dep = float(dm[current_node][depot]) / span

    # Clarke-Wright style saving: going current -> candidate -> depot
    # versus current -> depot directly then depot -> candidate.
    saving = d_cur_dep + d_dep - d_cur

    # Normalise demand to (0,1] to form a savings-per-demand density.
    safe_dem = np.maximum(dem, 1e-9)
    density = saving / safe_dem

    # Load-balancing: penalise candidates whose residual capacity after
    # service would be large relative to remaining capacity (over-serving
    # too early leaves awkward leftover), and also penalise tiny demand
    # usage that wastes the remaining trip.
    new_rest = np.maximum(cap - dem, 0.0)
    leftover_frac = new_rest / (cap + 1e-12)
    # Prefer moderate leftover: a mild U-shape around ~0.25 of capacity.
    balance = (leftover_frac - 0.25) ** 2

    # Combined score: maximise density, minimise imbalance.
    score = -density + 1.5 * balance
    return int(idx[np.argmin(score)])