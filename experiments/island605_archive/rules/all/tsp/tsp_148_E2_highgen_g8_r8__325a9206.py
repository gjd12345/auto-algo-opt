def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    # Distances from current node and destination node
    cur_dists = distance_matrix[current_node][unvisited_nodes]
    dest_dists = distance_matrix[destination_node][unvisited_nodes]

    # Normalize current distances to [0, 1]
    max_cur = np.max(cur_dists)
    min_cur = np.min(cur_dists)
    norm_cur = (cur_dists - min_cur) / (max_cur - min_cur + 1e-10)

    # Normalize destination distances to [0, 1]
    max_dest = np.max(dest_dists)
    min_dest = np.min(dest_dists)
    norm_dest = (dest_dists - min_dest) / (max_dest - min_dest + 1e-10)

    # Farthest-insertion factor: prefer nodes farther from destination (to visit early)
    farthest_factor = norm_dest  # 0 = close to dest, 1 = far from dest

    # 2-opt-aware smoothness penalty: prefer nodes where current->candidate is not too long
    # relative to candidate->destination (avoid creating a long sharp back-edge later)
    with np.errstate(divide='ignore', invalid='ignore'):
        ratio = np.where(dest_dists > 0, cur_dists / (dest_dists + 1e-10), np.inf)
    # Normalize ratio to [0,1] (lower is smoother)
    max_ratio = np.max(ratio)
    min_ratio = np.min(ratio)
    if max_ratio > min_ratio:
        norm_ratio = (ratio - min_ratio) / (max_ratio - min_ratio + 1e-10)
    else:
        norm_ratio = np.zeros_like(ratio)

    # Combined score: weighted sum of proximity to current (low is good), farthest (high is good),
    # and smoothness (low is good). We want low overall score.
    alpha = 0.4
    beta = 0.3
    gamma = 0.3
    scores = alpha * norm_cur - beta * farthest_factor + gamma * norm_ratio

    best_idx = np.argmin(scores)
    return unvisited_nodes[best_idx]
