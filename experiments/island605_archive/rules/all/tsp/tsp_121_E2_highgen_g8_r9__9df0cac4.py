def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    dist_current = distance_matrix[current_node][unvisited_nodes]
    best_score = float('inf')
    best_node = unvisited_nodes[0]

    for i, u in enumerate(unvisited_nodes):
        remaining = np.setdiff1d(unvisited_nodes, [u])
        if len(remaining) < 2:
            centrality = 0
        else:
            # Compute sum of distances from u to all remaining nodes (degree-like in weighted graph)
            degree_sum = np.sum(distance_matrix[u][remaining])
            # Compute sum of distances among remaining nodes
            intra_sum = 0
            for v in remaining:
                intra_sum += np.sum(distance_matrix[v][remaining])
            intra_sum /= 2  # each pair counted twice
            # Laplacian-like centrality: high if u is strongly connected to others
            centrality = degree_sum / (intra_sum + 1e-8)

        travel_cost = dist_current[i]
        # Score: prefer high centrality (minimize travel_cost / centrality)
        score = travel_cost / (centrality + 1e-8)

        if score < best_score:
            best_score = score
            best_node = u

    return int(best_node)
