def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        # Far-first seeding: prefer distant customers
        depot_distances = distance_matrix[depot][unvisited_nodes]
        farthest_idx = np.argmax(depot_distances)
        return unvisited_nodes[farthest_idx]
    else:
        best_score = -np.inf
        best_node = depot
        for u in unvisited_nodes:
            d_curr = distance_matrix[current_node][u]
            d_depot = distance_matrix[current_node][depot]
            # Weighted score: favor traveling to a customer vs returning to depot
            # Higher weight on depot proximity to encourage route completion
            score = -d_curr + 0.7 * d_depot
            # Small bonus for distant nodes from depot to spread routes
            score += 0.1 * distance_matrix[depot][u]
            if score > best_score:
                best_score = score
                best_node = u
        # Return depot only if it is clearly better than the best customer
        if distance_matrix[current_node][depot] < -best_score + 1e-6:
            return depot
        return best_node
