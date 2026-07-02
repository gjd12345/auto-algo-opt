"""TSP Construct — 历史最优代码 (best=6.287, gen=4, pop=8)

来源: literature_rag, cards=[tsp_regret_insertion, tsp_farthest_insertion]
策略: 结合 regret lookahead + farthest isolation + centroid centrality
"""
import numpy as np


def select_next_node(current_node: int, destination_node: int,
                     unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a TSP greedy construction."""
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    relevant_nodes = np.append(unvisited_nodes, destination_node)
    avg_distances = []
    for u in unvisited_nodes:
        others = np.setdiff1d(relevant_nodes, [u])
        avg_dist = np.mean([distance_matrix[u][o] for o in others])
        avg_distances.append(avg_dist)

    scores = []
    regrets = []

    for i, cand in enumerate(unvisited_nodes):
        d_current = distance_matrix[current_node][cand]
        iso_factor = avg_distances[i]

        two_hop_min = np.inf
        for j, k in enumerate(unvisited_nodes):
            if k == cand:
                continue
            two_hop = distance_matrix[current_node][k] + distance_matrix[k][cand]
            if two_hop < two_hop_min:
                two_hop_min = two_hop

        if two_hop_min == np.inf:
            regret_val = 0.0
        else:
            regret_val = max(0.0, two_hop_min - d_current)

        w_iso = 0.4
        w_regret = 0.6
        scores.append((w_iso * iso_factor + w_regret * regret_val) / (d_current + 1e-9))
        regrets.append(regret_val)

    if np.max(regrets) == 0.0:
        best_idx = np.argmin(distance_matrix[current_node][unvisited_nodes])
        min_dists = distance_matrix[current_node][unvisited_nodes]
        mask = min_dists == min_dists[best_idx]
        if np.sum(mask) > 1:
            tied_indices = np.where(mask)[0]
            best_tie_idx = tied_indices[np.argmax([avg_distances[t] for t in tied_indices])]
            return unvisited_nodes[best_tie_idx]
        return unvisited_nodes[best_idx]

    best_score_idx = np.argmax(scores)
    return unvisited_nodes[best_score_idx]
