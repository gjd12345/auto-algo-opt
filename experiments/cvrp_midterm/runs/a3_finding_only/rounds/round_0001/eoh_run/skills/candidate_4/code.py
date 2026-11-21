def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    far = float(np.max(d_dep)) if d_dep.size else 0.0
    scale = far if far > 0.0 else 1.0
    score = (d_cur + d_dep) / scale
    return int(unvisited_nodes[int(np.argmin(score))])