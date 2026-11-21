def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    # Primary: Clarke-Wright savings (larger savings => better to insert now)
    savings = distance_matrix[current_node][depot] + d_dep - d_cur

    # Capacity-aware bonus: prefer larger demands when savings are close
    cap_ratio = dem / max(rest_capacity, 1e-12)
    score = savings + 0.05 * cap_ratio * (d_dep + d_cur)

    best_idx = int(np.argmax(score))

    # Secondary ordering: among near-tied candidates, pick closest to current node
    tied = np.where(np.isclose(score, score[best_idx], rtol=1e-6, atol=1e-9))[0]
    if tied.size > 1:
        best_idx = int(tied[np.argmin(d_cur[tied])])

    return int(unvisited_nodes[best_idx])