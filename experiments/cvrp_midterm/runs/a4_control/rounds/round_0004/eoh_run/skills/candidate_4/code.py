def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
    dem = demands[unvisited_nodes].astype(float)
    cap = max(rest_capacity, 1e-9)

    # Geometric density: reward high demand per unit of combined travel cost
    density = dem / (d_cur + d_dep + 1e-9)

    # Angular alignment: prefer nodes that continue the current direction
    if current_node != depot:
        vx = distance_matrix[current_node] - distance_matrix[depot]
        # cheap proxy: use distances only, approximate alignment via cosine on distance vectors
        cur_dep = distance_matrix[depot][current_node]
        cos_align = (cur_dep**2 + d_dep**2 - d_cur**2) / (2.0 * cur_dep * d_dep + 1e-9)
        cos_align = np.clip(cos_align, -1.0, 1.0)
    else:
        cos_align = np.ones_like(d_cur)

    # Combine: dense, aligned, and load-fill aware
    fill = dem / cap
    scores = -(density * (0.5 + 0.5 * cos_align) + 0.3 * fill)

    return int(unvisited_nodes[np.argmin(scores)])