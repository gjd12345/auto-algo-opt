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
    load_pressure = dem / cap

    # Primary score: normalized NN distance, depot foreshortening, squared load bonus.
    primary = (d_cur / scale) + 0.15 * (d_dep / scale) - 0.25 * load_pressure

    # Second stage: only re-rank within a narrow relative band of the best primary.
    best = float(np.min(primary))
    band = max(abs(best), 1e-9) * 0.02 + 1e-6
    in_band = primary <= best + band

    # Within the band, prefer the node that consumes more remaining capacity
    # (larger load pressure), tie-broken by smaller travel distance.
    secondary = np.where(in_band, -load_pressure + 0.01 * (d_cur / scale), np.inf)

    return int(unvisited_nodes[np.argmin(secondary)])