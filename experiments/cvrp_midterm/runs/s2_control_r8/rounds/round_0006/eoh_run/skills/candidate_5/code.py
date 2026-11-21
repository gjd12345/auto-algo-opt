def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    nodes = np.asarray(unvisited_nodes)
    d_cur = distance_matrix[current_node][nodes].astype(np.float64)
    d_dep_next = distance_matrix[depot][nodes].astype(np.float64)
    d_cur_dep = float(distance_matrix[current_node][depot])
    dem = demands[nodes].astype(np.float64)

    cap = float(rest_capacity) if rest_capacity > 0 else 1.0

    # Regret: extra cost of inserting node now vs. straight return to depot.
    # Positive regret means detour; negative would be a shortcut (rare but possible
    # if current_node isn't the depot; clamp sign behavior naturally).
    regret = d_cur + d_dep_next - d_cur_dep

    # Capacity fit: leftover fraction after serving this node.
    leftover = np.clip(cap - dem, 0.0, cap) / (cap + 1e-9)
    # Prefer nodes that leave little slack (tight packing) -> reward low leftover
    # but not so tight it strands far nodes; use a mild quadratic shaping.
    fit = 1.0 - leftover * leftover

    # Normalize regret by local distance scale to keep terms comparable.
    scale = d_cur_dep + d_cur + d_dep_next + 1e-9
    regret_norm = regret / scale

    # Composite: minimize regret, modulated upward when packing is poor.
    score = regret_norm - 0.5 * fit

    idx = int(np.argmin(score))
    return int(nodes[idx])