def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    import numpy as np

    # At depot: seed route with farthest customer to reach distant clusters
    if current_node == depot:
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]

    # Compute polar angle proxy from depot using distance matrix and index
    depot_dist_current = distance_matrix[depot][current_node]
    depot_dists = distance_matrix[depot][unvisited_nodes]
    # Angular similarity: prefer nodes with depot distance close to current node's depot distance
    angle_cost = 0.7 * np.abs(depot_dists - depot_dist_current)

    # Distance from current node weighted by capacity usage
    dists = distance_matrix[current_node][unvisited_nodes]
    demands_local = demands[unvisited_nodes]
    capacity_penalty = 0.2 * (demands_local / rest_capacity)
    weighted_dists = dists * (1.0 + capacity_penalty)

    # Combined score
    combined = weighted_dists + angle_cost

    return unvisited_nodes[np.argmin(combined)]
