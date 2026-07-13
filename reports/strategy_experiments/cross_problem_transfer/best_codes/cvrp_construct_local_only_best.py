# 正式证据来源: cross_problem_transfer/cvrp_construct/local_only/3104
# Core/primary held-out score: 16.0917942644
def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Seed route: among farthest 30% of feasible customers, pick the one with highest regret
        distances_from_depot = distance_matrix[depot][unvisited_nodes]
        threshold = np.percentile(distances_from_depot, 70)
        far_indices = np.where(distances_from_depot >= threshold)[0]
        far_nodes = unvisited_nodes[far_indices]
        best_regret = -1
        best_node = unvisited_nodes[np.argmax(distances_from_depot)]
        for u in far_nodes:
            # Compute best and second-best insertion detour from depot to u
            detours = []
            for v in unvisited_nodes:
                if v == u:
                    continue
                detour = distance_matrix[depot][u] + distance_matrix[u][v] - distance_matrix[depot][v]
                detours.append(detour)
            if len(detours) >= 2:
                sorted_detours = np.sort(detours)
                regret = sorted_detours[1] - sorted_detours[0]
                if regret > best_regret:
                    best_regret = regret
                    best_node = u
        return best_node
    else:
        capacity_ratio = rest_capacity / (demands.max() * 2 + 1e-6)
        if capacity_ratio > 0.4:
            # Savings-based: max (dist(depot,u) + dist(depot,current) - dist(current,u))
            savings = (distance_matrix[depot][unvisited_nodes] +
                       distance_matrix[depot][current_node] -
                       distance_matrix[current_node][unvisited_nodes])
            return unvisited_nodes[np.argmax(savings)]
        else:
            # Low capacity: return to depot unless nearest customer is very close
            nearest = unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
            if distance_matrix[current_node][nearest] < distance_matrix[current_node][depot] * 0.7:
                return nearest
            else:
                return depot
