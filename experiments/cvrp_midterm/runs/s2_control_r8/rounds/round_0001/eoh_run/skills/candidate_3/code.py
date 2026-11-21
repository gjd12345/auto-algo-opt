def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction.

    Args:
        current_node:    index of the current node (0 = depot)
        depot:           index of the depot (always 0)
        unvisited_nodes: array of feasible unvisited customer indices
                         (already filtered to satisfy remaining capacity)
        rest_capacity:   remaining vehicle capacity
        demands:         demand of every node (index 0 = depot demand = 0)
        distance_matrix: pairwise Euclidean distance matrix
    Returns:
        Index of the next node to visit, or 0 to return to the depot early.
    """
    if unvisited_nodes.size == 0:
        return 0
    if unvisited_nodes.size == 1:
        return int(unvisited_nodes[0])

    nodes = np.asarray(unvisited_nodes)
    dep = int(depot)
    cur = int(current_node)

    # Angular position of each candidate around the depot (from distance matrix
    # alone we approximate geometry via the law of cosines using depot distances
    # and inter-node distances).  Fall back to distance-based ordering if the
    # geometry is degenerate.
    d_dep = distance_matrix[dep][nodes].astype(float)
    d_cur = distance_matrix[cur][nodes].astype(float)

    # We build a "sweep progress" measure: prefer nodes roughly at 60-120 deg
    # turn from the current heading.  Without coordinates, use the triangle
    # relation cos(theta) = (d_cur_dep^2 + d_dep^2 - d_cur^2) / (2*d_cur_dep*d_dep)
    # where theta is the angle at the depot between current node and candidate.
    d_cur_dep = float(distance_matrix[cur][dep])
    eps = 1e-9
    denom = 2.0 * d_cur_dep * d_dep + eps
    cos_theta = (d_cur_dep * d_cur_dep + d_dep * d_dep - d_cur * d_cur) / denom
    cos_theta = np.clip(cos_theta, -1.0, 1.0)
    theta = np.arccos(cos_theta)  # angle at depot between cur and candidate

    # Sweep preference: continue forward but with a moderate turn (avoid going
    # straight back and avoid sharp reversals).  Peak preference near 1.0 rad.
    sweep_score = 1.0 - np.abs(theta - 1.0)

    # Proximity to current node (concave advantage so nearby nodes dominate).
    prox = -np.log(d_cur + 1.0)

    # Capacity-fill urgency: if remaining capacity is tight relative to demands,
    # prefer larger demands to fill the load; otherwise mild preference for
    # smaller demands to keep options open.
    dem = demands[nodes].astype(float)
    cap = max(float(rest_capacity), eps)
    fill_ratio = dem / cap
    slack = cap - np.sum(dem)
    if slack < 0.35 * cap:
        cap_score = fill_ratio  # tight: prefer big demands
    else:
        cap_score = -0.3 * fill_ratio  # loose: mild preference for small

    score = 1.0 * sweep_score + 0.5 * prox + 0.4 * cap_score

    best_local = int(np.argmax(score))
    return int(nodes[best_local])