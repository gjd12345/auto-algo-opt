import numpy as np

def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        # Start a new route: select farthest feasible customer
        farthest_idx = np.argmax(distance_matrix[depot, unvisited_nodes])
        return unvisited_nodes[farthest_idx]
    else:
        # Compute a score combining distance from current node (lower is better)
        # and angular similarity to the previous direction from depot.
        # Use distance from depot and cross-node distance to approximate angular coherence.
        prev_node = current_node  # treat current_node as previous visited
        depot_dists = distance_matrix[depot, unvisited_nodes]
        curr_dists = distance_matrix[current_node, unvisited_nodes]
        cross_dists = distance_matrix[current_node, unvisited_nodes]  # placeholder
        # For angular similarity, prefer nodes where distances to depot and to current
        # have similar ratio (indicating similar bearing from depot).
        # Use ratio of depot distance to current distance as a proxy for angular alignment.
        # Avoid division by zero.
        ratio = np.where(curr_dists > 0, depot_dists / curr_dists, 0)
        # Normalize components
        max_ratio = np.max(ratio) if len(ratio) > 0 else 1
        if max_ratio == 0:
            max_ratio = 1
        max_curr = np.max(curr_dists) if len(curr_dists) > 0 else 1
        if max_curr == 0:
            max_curr = 1
        # Score: prefer high ratio (similar bearing) and low current distance
        scores = (ratio / max_ratio) - (curr_dists / max_curr)
        best_idx = np.argmax(scores)
        return unvisited_nodes[best_idx]
