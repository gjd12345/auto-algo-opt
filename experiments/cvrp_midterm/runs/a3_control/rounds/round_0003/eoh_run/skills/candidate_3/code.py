def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_depot = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]
    cap = rest_capacity if rest_capacity > 1e-9 else 1.0

    n = unvisited_nodes.size
    scale = float(np.mean(d_cur) + np.mean(d_depot) + 1.0)

    best_score = None
    best_idx = int(unvisited_nodes[0])

    for i in range(n):
        node_i = unvisited_nodes[i]
        if n > 1:
            mask = np.ones(n, dtype=bool)
            mask[i] = False
            follow = float(np.min(distance_matrix[node_i][unvisited_nodes[mask]]))
        else:
            follow = 0.0

        # Savings of serving i now versus a separate depot round-trip
        savings = d_depot[i] + d_depot[i] - (d_cur[i] + follow)

        # Nearest-neighbor proximity (smaller is better -> use negative)
        proximity = -d_cur[i] / scale

        # Prefer using capacity efficiently but not forcing near-full routes
        fill = dem[i] / cap
        fill_term = fill - 0.5 * fill * fill

        # Penalize nodes that would leave the vehicle far from depot at end
        far_penalty = -0.25 * (d_depot[i] / scale)

        score = (savings / scale) + proximity + 0.6 * fill_term + far_penalty

        if best_score is None or score > best_score:
            best_score = score
            best_idx = int(node_i)

    return best_idx