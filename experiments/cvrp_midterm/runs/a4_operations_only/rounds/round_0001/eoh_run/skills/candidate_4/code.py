def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    # savings-style: prefer nodes close to current and far from depot
    score = d_cur - d_dep
    # secondary ordering among near-ties: prefer larger demand
    best = np.min(score)
    tie = np.abs(score - best) <= 1e-9
    if np.any(tie):
        cand = unvisited_nodes[tie]
        cand_scores = score[tie]
        # among ties, largest demand first
        return int(cand[np.argmax(demands[cand])])
    return int(unvisited_nodes[np.argmin(score)])