def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    scale = float(np.max(distance_matrix[depot])) if distance_matrix.size else 1.0
    if scale <= 0.0:
        scale = 1.0

    cap = float(rest_capacity) if rest_capacity > 0.0 else 1.0
    load_frac = np.clip(dem / cap, 0.0, 1.0)

    cur_pos = distance_matrix[current_node][depot]
    d_curdepot_savings = (d_cur + d_dep - cur_pos) / scale

    # Primary: nearest-neighbour distance, with a load-weighted radial pull
    # that encourages serving customers closer to the depot sooner so that
    # remaining far customers are paired into efficient backhaul trips.
    primary = (d_cur / scale) - 0.15 * load_frac * (d_dep / scale) \
              + 0.10 * (1.0 - load_frac) * (d_cur / scale)

    best = float(np.min(primary))
    band = max(abs(best), 1e-9) * 0.10 + 1e-9

    # Inside the band, prefer the node with the best load-weighted savings
    # ratio (savings per unit distance), so nearly equivalent hops favour
    # the one that packs more demand into the route.
    ratio = d_curdepot_savings / (d_cur / scale + 1e-9)
    secondary = np.where(primary <= best + band,
                         -(ratio * (0.5 + 0.5 * load_frac)),
                         np.inf)

    return int(unvisited_nodes[np.argmin(secondary)])