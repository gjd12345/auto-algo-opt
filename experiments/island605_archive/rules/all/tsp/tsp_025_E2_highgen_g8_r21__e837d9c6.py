def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_node = unvisited_nodes[0]
    best_cost = float('inf')

    for u in unvisited_nodes:
        # Cost to go from current to candidate
        cost = distance_matrix[current_node][u]

        # Simulate visiting u, then greedily estimate remaining tour cost
        remaining = [v for v in unvisited_nodes if v != u]
        if remaining:
            # Nearest neighbor from u
            nn_u = min(remaining, key=lambda v: distance_matrix[u][v])
            cost += distance_matrix[u][nn_u]

            # Greedy chain through remaining nodes
            prev = nn_u
            temp_remaining = [v for v in remaining if v != nn_u]
            while temp_remaining:
                next_n = min(temp_remaining, key=lambda v: distance_matrix[prev][v])
                cost += distance_matrix[prev][next_n]
                prev = next_n
                temp_remaining.remove(next_n)

            # Return to destination from last node
            cost += distance_matrix[prev][destination_node]
        else:
            # Only candidate left, go directly to destination
            cost += distance_matrix[u][destination_node]

        if cost < best_cost:
            best_cost = cost
            best_node = u

    return int(best_node)
