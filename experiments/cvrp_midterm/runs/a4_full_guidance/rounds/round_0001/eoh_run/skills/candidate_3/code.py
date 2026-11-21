def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]
    cap = rest_capacity if rest_capacity > 0 else 1.0
    # capacity term replaced: normalized demand pressure (prefer large demands
    # relative to remaining capacity to fill the vehicle efficiently)
    cap_term = dem / cap
    scores = d_cur + d_dep - cap_term * (d_cur.mean() + d_dep.mean()) * 0.0
    # keep effect readable: pure ratio term added to distances
    scores = d_cur + d_dep + (cap - dem) / cap * (d_cur + d_dep).std() if (d_cur.size and (d_cur + d_dep).std() > 0) else d_cur + d_dep
    # simpler, scale-normalized capacity term: penalty proportional to remaining slack fraction
    slack = (cap - dem) / cap
    scale = np.median(d_cur + d_dep) + 1e-12
    scores = d_cur + d_dep + slack * scale
    return int(unvisited_nodes[int(np.argmin(scores))])