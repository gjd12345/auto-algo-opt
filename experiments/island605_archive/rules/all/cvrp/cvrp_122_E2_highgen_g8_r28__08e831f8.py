def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction.

    Args:
        current_node:    index of the current node (0 = depot)
        depot:           index of the depot (always 0)
        unvisited_nodes: array of feasible unvisited customer indices
                         (already filtered to satisfy remaining capacity)
        rest_capacity:   remaining vehicle capacity
        demands:         demand of every node (index 0 = depot demand = 0)
        distance_matrix: pairwise Euclidean distance matrix
    Returns:
        Index of the next node to visit, or 0 to return to the depot early.
    """
    import numpy as np

    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        # Seed route: prefer farthest feasible customer
        dists = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists)]

    # Compute savings: dist(current, depot) + dist(depot, u) - dist(current, u)
    dist_current_depot = distance_matrix[current_node][depot]
    savings = dist_current_depot + distance_matrix[depot][unvisited_nodes] - distance_matrix[current_node][unvisited_nodes]

    # Regret: for each unvisited node, compute the difference between the best and second-best
    # insertion cost if we were to insert it into a route from current_node
    # Here we approximate regret by: best insertion cost = distance(current_node, u)
    # second-best insertion cost = min over other unvisited nodes of distance(u, v) + distance(current_node, v) - distance(current_node, u)
    # To keep it bounded and simple, we use: regret = second_min_dist - min_dist, where
    # min_dist = distance_matrix[current_node][u]
    # second_min_dist = min_{v != u} distance_matrix[u][v] (approximated by the minimum distance from u to any other feasible node)
    n = len(unvisited_nodes)
    min_dist = distance_matrix[current_node][unvisited_nodes]
    second_min_dist = np.full(n, np.inf)
    for i, u in enumerate(unvisited_nodes):
        # Distance from u to all other unvisited nodes
        others = unvisited_nodes[unvisited_nodes != u]
        if len(others) > 0:
            second_min_dist[i] = np.min(distance_matrix[u][others])
        else:
            second_min_dist[i] = min_dist[i]  # fallback if no others
    regret = second_min_dist - min_dist
    # Normalize regret by its maximum to avoid scale issues
    max_regret = np.max(regret) if np.max(regret) > 0 else 1.0
    regret_norm = regret / max_regret

    # Normalize savings
    max_sav = np.max(savings) if np.max(savings) > 0 else 1.0
    savings_norm = savings / max_sav

    # Combined score: savings (efficiency) + 0.3 * regret (avoid postponing high-regret nodes)
    score = savings_norm + 0.3 * regret_norm
    best_idx = np.argmax(score)
    return unvisited_nodes[best_idx]
