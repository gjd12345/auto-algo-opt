def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return 0

    nodes = np.asarray(unvisited_nodes)
    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    dem = demands[nodes].astype(float)

    # Scale reference: max depot distance among candidates (guaranteed > 0 since depot != customers)
    scale = float(np.max(d_dep))
    if scale <= 0.0:
        scale = 1.0

    cap = float(rest_capacity) if rest_capacity > 0.0 else 1.0

    if current_node == depot:
        # Depot-start: scale-free radial-load seed rule.
        # Prefer far customers weighted by their demand share of remaining capacity.
        dem_share = dem / cap  # dimensionless in [0, 1]
        score = (d_dep / scale) - 0.5 * dem_share
    else:
        # Mid-route: dimensionless combination of normalized current distance,
        # moderate depot pull, and capacity-fill modulation.
        dem_share = dem / cap  # dimensionless
        score = (d_cur / scale) - 0.6 * (d_dep / scale) - 0.3 * dem_share

    best_idx = int(np.argmin(score))
    return int(nodes[best_idx])