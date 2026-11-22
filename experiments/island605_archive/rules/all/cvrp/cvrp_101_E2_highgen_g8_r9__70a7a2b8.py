def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    import numpy as np

    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        # Start new route: seed with farthest customer from depot
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]

    # Compute savings ratio: distance_from_depot / distance_from_current
    dists_from_depot = distance_matrix[depot][unvisited_nodes]
    dists_from_current = distance_matrix[current_node][unvisited_nodes]
    # Avoid division by zero; add small epsilon to denominator
    savings_ratio = dists_from_depot / (dists_from_current + 1e-10)

    # If rest_capacity is low (less than half of max demand in unvisited), prefer nearest
    max_demand = np.max(demands[unvisited_nodes])
    if rest_capacity < max_demand * 2:
        return unvisited_nodes[np.argmin(dists_from_current)]
    else:
        return unvisited_nodes[np.argmax(savings_ratio)]
