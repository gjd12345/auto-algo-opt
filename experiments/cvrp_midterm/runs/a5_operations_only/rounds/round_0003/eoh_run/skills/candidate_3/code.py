def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
    dem = demands[unvisited_nodes].astype(float)

    cap = float(rest_capacity) if rest_capacity > 1e-12 else 1e-12
    eps = 1e-9

    # Clarke-Wright style savings, scaled by round-trip depot distance.
    d_cur_depot = float(distance_matrix[current_node][depot])
    savings = d_cur_depot + d_dep - d_cur
    scale = (d_cur_depot + d_dep + eps)
    savings_term = savings / scale  # roughly (-1, 1]

    # Hyperbolic capacity-fit gate (unchanged form from incumbent).
    fit = np.abs(dem - cap) / (cap + eps)
    pressure = 1.0 / (1.0 + fit)

    # Primary: maximize savings and capacity pressure; slight detour penalty.
    primary = -(1.0 * savings_term + 0.9 * pressure) + 0.05 * (d_cur / (cap + eps))

    best_val = primary.min()
    tol = 1e-3
    close_mask = primary <= best_val + tol
    close = np.where(close_mask)[0]

    if close.size > 1:
        candidates = unvisited_nodes[close]
        c_cur = distance_matrix[current_node][candidates].astype(float)
        c_dep = distance_matrix[depot][candidates].astype(float)
        # Estimated extra route length if we insert this customer next.
        extension = c_cur + c_dep - (d_cur_depot + c_dep - c_cur)
        extension = extension + 0.5 * c_dep
        score2 = np.power(np.clip(extension, 1e-9, None), 1.5)
        return int(candidates[int(np.argmin(score2))])

    return int(unvisited_nodes[int(np.argmin(primary))])