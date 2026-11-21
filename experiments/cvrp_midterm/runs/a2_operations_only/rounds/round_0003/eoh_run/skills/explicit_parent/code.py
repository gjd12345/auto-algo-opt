def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    order = np.argsort(d_cur)
    # secondary ordering only among near-ties of the primary savings score
    savings = d_dep - d_cur
    return unvisited_nodes[np.argmax(savings)]