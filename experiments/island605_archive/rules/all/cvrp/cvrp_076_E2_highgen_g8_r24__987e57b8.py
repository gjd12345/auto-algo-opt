def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Starting a new route: pick the farthest customer to seed a cluster
        farthest_dist = -1
        farthest_node = depot
        for u in unvisited_nodes:
            d = distance_matrix[depot][u]
            if d > farthest_dist:
                farthest_dist = d
                farthest_node = u
        return farthest_node
    else:
        # Already on a route: compute polar angles from depot for all unvisited nodes
        import math
        def angle_from_depot(node):
            # Assuming coordinates are stored in distance_matrix as Euclidean distances from depot,
            # we need actual coordinates. Since we don't have them, we use a geometric proxy:
            # use distance_matrix[current_node][node] as proxy for angular proximity?
            # Instead, use a deterministic sweep based on distance from depot and current_node.
            # We'll pick the unvisited node that is closest in terms of distance from current_node,
            # but prefer those with similar distance from depot as current_node.
            return abs(distance_matrix[depot][node] - distance_matrix[depot][current_node])

        best_node = depot
        best_score = float('inf')
        for u in unvisited_nodes:
            # Score combines angular proxy (difference in depot-distance) and actual distance from current
            score = angle_from_depot(u) * 0.5 + distance_matrix[current_node][u] * 0.5
            if score < best_score:
                best_score = score
                best_node = u
        # Fallback: if best_node is depot or not better than returning to depot, check depot distance
        if best_node == depot:
            # no feasible customer found (should not happen)
            return depot
        # Only go to customer if it's beneficial vs returning to depot
        if distance_matrix[current_node][best_node] < distance_matrix[current_node][depot]:
            return best_node
        else:
            return depot
