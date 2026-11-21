def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    if current_node == depot:
        return int(unvisited_nodes[np.argmin(distance_matrix[unvisited_nodes, depot])])

    cur = distance_matrix[current_node][unvisited_nodes]
    to_depot = distance_matrix[unvisited_nodes, depot]
    stem = distance_matrix[current_node, depot]

    # Radial progress: prefer moving outward from depot (span-normalised)
    progress = to_depot - stem
    span = np.max(to_depot) - np.min(to_depot) + 1e-12
    outward = -progress / span  # negative => outward is good (minimised)

    dem = demands[unvisited_nodes]
    fill = dem / (rest_capacity + dem + 1e-12)

    rmax = np.max(cur) + 1e-12
    near = cur / rmax

    score = 0.6 * near + 0.5 * outward - 0.4 * fill
    return int(unvisited_nodes[np.argmin(score)])