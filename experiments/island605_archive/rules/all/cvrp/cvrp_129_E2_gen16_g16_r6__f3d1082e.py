def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    if current_node == depot:
        # Seed route with customer having highest distance-from-depot to distance-from-depot ratio
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        # Use ratio heuristic: prefer far customers but also those relatively close to depot direction
        # Here: simple farthest-first as baseline
        return unvisited_nodes[np.argmax(dists_from_depot)]
    else:
        # Weighted selection: 0.6 * savings (dist_to_depot - dist_from_current) + 0.4 * (-dist_from_current)
        dist_from_current = distance_matrix[current_node][unvisited_nodes]
        dist_to_depot = distance_matrix[depot][unvisited_nodes]
        savings = dist_to_depot - dist_from_current
        # Avoid divide-by-zero, add small epsilon
        score = 0.6 * savings - 0.4 * dist_from_current
        return unvisited_nodes[np.argmax(score)]
