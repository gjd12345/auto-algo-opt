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

    # Saturating remainder-after-service deficit: prefers customers leaving
    # a small but nonzero remainder (good packing behavior).
    rem = cap - dem
    rem_pos = np.where(rem >= 0.0, rem, 0.0)
    pack = 1.0 - rem_pos / cap  # in (0,1]; near 1 = well-packed
    pack_factor = pack / (1.0 + pack)

    # Additive normalized primary score: current distance dominates,
    # depot proximity moderates, packing pulls toward fuller loads.
    primary = (d_cur / scale) * 1.0 + 0.30 * (d_dep / scale) - 0.55 * pack_factor

    best = float(np.min(primary))
    band = abs(best) * 0.025 + 1e-6
    in_band = primary <= best + band

    # Narrow tie-break within band: larger demand, shorter detour, near depot.
    secondary = np.where(
        in_band,
        -0.90 * pack_factor + 0.10 * (d_cur / scale) + 0.05 * (d_dep / scale),
        np.inf,
    )

    return int(unvisited_nodes[np.argmin(secondary)])