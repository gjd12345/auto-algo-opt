def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_cur_dep = distance_matrix[current_node][depot]
    dem = demands[unvisited_nodes].astype(float)

    cap = max(rest_capacity, 1e-9)
    fill = np.clip(dem / cap, 0.0, 1.0)

    # Savings-style: serving this customer vs. returning to depot now
    savings = d_cur_dep + d_dep - d_cur
    # Wait, standard savings is d(i,depot)+d(depot,j)-d(i,j); here analogous blend
    score = d_cur - 0.35 * savings - 0.25 * fill * d_dep + 0.15 * fill * d_cur_dep

    return int(unvisited_nodes[np.argmin(score)])