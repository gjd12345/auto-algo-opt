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

    # Primary score: normalized NN distance, stronger depot foreshortening,
    # cubic load bonus to favor fuller loads.
    primary = (d_cur / scale) + 0.25 * (d_dep / scale) - 0.40 * (load_pressure ** 3)

    # Second stage: re-rank within a slightly wider relative band of the best.
    best = float(np.min(primary))
    band = max(abs(best), 1e-9) * 0.03 + 1e-6
    in_band = primary <= best + band

    # Within the band, prefer higher load consumption; penalize longer travel.
    secondary = np.where(in_band, -0.6 * load_pressure + 0.05 * (d_cur / scale), np.inf)

    return int(unvisited_nodes[np.argmin(secondary)])