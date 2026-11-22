def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    best_score = -float('inf')
    best_node = unvisited_nodes[0]

    for u in unvisited_nodes:
        d_cur_u = distance_matrix[current_node][u]
        d_u_dest = distance_matrix[u][destination_node]
        d_cur_dest = distance_matrix[current_node][destination_node]

        # Regret term
        others = [distance_matrix[u][v] for v in unvisited_nodes if v != u]
        if len(others) >= 2:
            others.sort()
            regret = others[1] - others[0]
        else:
            regret = 0.0

        # Convexity penalty: penalize if angle is sharp (using triangle inequality deviation)
        if d_cur_u + d_u_dest > 0:
            convexity = abs(d_cur_u + d_u_dest - d_cur_dest) / (d_cur_u + d_u_dest + 1e-10)
        else:
            convexity = 0.0

        # Product score: favor nodes with large (dest distance - current distance) and high regret, penalize sharp turns
        score = (d_u_dest - d_cur_u) * (1.0 + regret) / (1.0 + 2.0 * convexity)

        if score > best_score:
            best_score = score
            best_node = u
        elif abs(score - best_score) < 1e-10 and d_cur_u < distance_matrix[current_node][best_node]:
            best_node = u

    return best_node
