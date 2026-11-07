def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_dep = distance_matrix[depot][unvisited_nodes]

    if current_node == depot:
        return int(unvisited_nodes[np.argmax(d_dep)])

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_back = distance_matrix[current_node][depot]
    detour = d_cur + d_dep - d_back

    # Relative detour: small when heading homeward-ish, used as a soft pull to depot.
    scale = d_cur + d_dep + 1e-9
    pull_home = d_dep / scale

    # Capacity pressure: favors customers that help close out the load.
    cap_ratio = rest_capacity / (rest_capacity + float(np.sum(demands[unvisited_nodes])) + 1e-9)

    scores = (0.5 * d_cur
              - 0.35 * detour
              + 0.4 * cap_ratio * pull_home * d_cur
              + 0.15 * (1.0 - cap_ratio) * d_dep)

    return int(unvisited_nodes[np.argmin(scores)])