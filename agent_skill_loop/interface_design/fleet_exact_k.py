"""Budgeted Clarke–Wright construction with exact-fleet packing and repair."""

from __future__ import annotations

import bisect
import numbers
import time
from collections.abc import Mapping

import numpy as np

from .contracts import ALLOWED_POSTPROCESS_MODES, LEGACY_CVRP_PROTOCOL_ID, HookSpec
from .templates import (
    CLASSIC_CW_STATIC_HOOK_CODE,
    TemplateSpec,
    _effective_solve_deadline,
    _find_relocate_destination_guarded,
    _two_opt_single_route_guarded,
    apply_relocate_2opt_guarded,
    compute_template_source_sha256,
    register_template,
)

FLEET_EXACT_K_TEMPLATE_KEY = ("cvrp_fleet_aware_exact_k", "v1")
_STATIC = HookSpec(
    "score_merge_static", ("distance_matrix", "demands", "capacity", "i_idx", "j_idx"), "i_idx",
)
_ADJUSTMENT = HookSpec(
    "score_fleet_adjustment",
    ("base_rank", "savings_scaled", "load_i_frac", "load_j_frac", "residual_after_frac",
     "endpoint_demand_i_frac", "endpoint_demand_j_frac", "target_k", "route_count", "rho"),
    "base_rank",
)
EPS = 1e-12
BLOCK_SIZE = 64
ADJUSTMENT_HEADER = f"def {_ADJUSTMENT.name}({', '.join(_ADJUSTMENT.signature)}):\n"
BASELINE_ADJUSTMENT_CODE = (
    "import numpy as np\n" + ADJUSTMENT_HEADER + "    return np.zeros_like(base_rank, dtype=np.float64)\n"
)
_BASELINE_PROGRAM = CLASSIC_CW_STATIC_HOOK_CODE + "\n" + BASELINE_ADJUSTMENT_CODE.split("\n", 1)[1]
FLEET_EXACT_K_MOCK_CANDIDATES = tuple(
    CLASSIC_CW_STATIC_HOOK_CODE + "\n" + ADJUSTMENT_HEADER + f"    return {expression}\n"
    for expression in (
        "0.6 * (load_i_frac + load_j_frac) + 0.15 * savings_scaled",
        "0.3 * np.abs(load_i_frac - load_j_frac) + 0.5 * savings_scaled",
        "0.4 * (endpoint_demand_i_frac + endpoint_demand_j_frac) - 0.25 * residual_after_frac",
    )
)


def _cost(routes, dmat):
    return float(sum(
        dmat[0, route[0]] + sum(dmat[a, b] for a, b in zip(route, route[1:])) + dmat[route[-1], 0]
        for route in routes
    ))


def _loads(routes, demands):
    return [sum(float(demands[node]) for node in route) for route in routes]


def _read_only(values):
    view = values.view()
    view.flags.writeable = False
    return view


def _scores(hook, args, size):
    values = np.asarray(hook(*args))
    if values.shape != (size,) or values.dtype.kind not in "iuf":
        raise ValueError(f"invalid_return:expected_finite_numeric_shape=({size},)")
    if not np.isfinite(values).all():
        raise ValueError("nonfinite_hook_scores")
    return values.astype(np.float64, copy=False)


def _construct(dmat, demands, capacity, static, adjustment, target, rho, deadline, capture):
    """Consume the static order in windows, reranking 64 live edges at a time."""
    n = len(demands) - 1
    routes = {i: [i] for i in range(1, n + 1)}
    owner = np.arange(n + 1)
    loads = demands.copy()
    endpoint = np.ones(n + 1, dtype=bool)
    seq = []
    diag = dict(
        static_scores_vary=False, adjustment_features_vary=False, adjustment_scores_vary=False,
        adjustment_is_zero=True, positive_savings_pairs=0, static_positive_savings_pairs=0,
    )
    timing = dict(candidate_gen_ms=0.0, hook_ms=0.0, merge_ms=0.0, hook_call_count=0, merges_applied=0)
    if n < 2 or len(routes) == target or time.perf_counter() >= deadline:
        return list(routes.values()), seq, diag, timing

    started = time.perf_counter()
    i, j = np.triu_indices(n, 1)
    i += 1
    j += 1
    savings = dmat[0, i] + dmat[0, j] - dmat[i, j]
    positive = savings > EPS
    i, j, savings = i[positive], j[positive], savings[positive]
    timing["candidate_gen_ms"] = (time.perf_counter() - started) * 1000
    diag["static_positive_savings_pairs"] = len(i)
    if not len(i) or time.perf_counter() >= deadline:
        return list(routes.values()), seq, diag, timing

    started = time.perf_counter()
    scores = _scores(static, (_read_only(dmat), _read_only(demands), capacity, _read_only(i), _read_only(j)), len(i))
    timing["hook_ms"] = (time.perf_counter() - started) * 1000
    timing["hook_call_count"] = 1
    diag["static_scores_vary"] = bool(np.any(scores != scores[0]))
    if time.perf_counter() >= deadline:
        return list(routes.values()), seq, diag, timing

    started = time.perf_counter()
    order = np.argsort(-scores, kind="stable")
    savings_scale = float(savings.max())
    cursor = 0
    while cursor < len(order) and len(routes) != target and time.perf_counter() < deadline:
        window = order[cursor:cursor + 2048]
        a, b = i[window], j[window]
        ra, rb = owner[a], owner[b]
        live = np.flatnonzero(
            endpoint[a] & endpoint[b] & (ra != rb) & (loads[ra] + loads[rb] <= capacity + EPS)
        )
        if not len(live):
            cursor += len(window)
            continue
        if len(live) > BLOCK_SIZE:
            live = live[:BLOCK_SIZE]
            cursor += int(live[-1]) + 1
        else:
            cursor += len(window)
        pairs = window[live]
        a, b = i[pairs], j[pairs]
        if target is not None:
            rank = np.linspace(1.0, 0.0, len(pairs))
            load_a, load_b = loads[owner[a]] / capacity, loads[owner[b]] / capacity
            vectors = (
                rank, savings[pairs] / savings_scale, load_a, load_b, 1.0 - load_a - load_b,
                demands[a] / capacity, demands[b] / capacity,
            )
            if time.perf_counter() >= deadline:
                break
            hooked = time.perf_counter()
            adjustment_scores = _scores(
                adjustment, (*map(_read_only, vectors), target, len(routes), rho), len(pairs),
            )
            timing["hook_ms"] += (time.perf_counter() - hooked) * 1000
            timing["hook_call_count"] += 1
            if capture:
                diag["adjustment_features_vary"] |= any(np.any(v != v[0]) for v in vectors[1:])
                diag["adjustment_scores_vary"] |= bool(np.any(adjustment_scores != adjustment_scores[0]))
                diag["adjustment_is_zero"] &= not bool(np.any(adjustment_scores))
            reranked = np.argsort(-(rank + adjustment_scores), kind="stable")
            a, b = a[reranked], b[reranked]
        if time.perf_counter() >= deadline:
            break
        for left, right in zip(a.tolist(), b.tolist()):
            ra, rb = int(owner[left]), int(owner[right])
            if ra == rb or not (endpoint[left] and endpoint[right]) or loads[ra] + loads[rb] > capacity + EPS:
                continue
            first, second = routes[ra], routes.pop(rb)
            if first[-1] != left:
                first = first[::-1]
            if second[0] != right:
                second = second[::-1]
            merged = first + second
            endpoint[left] = first[0] == left
            endpoint[right] = second[-1] == right
            routes[ra] = merged
            loads[ra] += loads[rb]
            owner[second] = ra
            if capture:
                seq.append([left, right])
            if len(routes) == target:
                break
    timing["merges_applied"] = n - len(routes)
    timing["merge_ms"] = max(0.0, (time.perf_counter() - started) * 1000 - timing["hook_ms"])
    return list(routes.values()), seq, diag, timing


def _pack_first_fit(items, demands, capacity, deadline):
    """First fit in insertion order, using a max-residual segment tree."""
    size = 1 << max(0, (len(items) - 1).bit_length())
    tree = [-float("inf")] * (2 * size)
    bins = []
    for node in items:
        if time.perf_counter() >= deadline:
            return None
        weight = float(demands[node])
        if tree[1] < weight - EPS:
            slot = len(bins)
            bins.append([])
            tree[size + slot] = capacity
        else:
            k = 1
            while k < size:
                k *= 2
                if tree[k] < weight - EPS:
                    k += 1
            slot = k - size
        bins[slot].append(node)
        k = size + slot
        tree[k] -= weight
        while k > 1:
            k //= 2
            tree[k] = max(tree[2 * k], tree[2 * k + 1])
    return bins


def _pack_best_fit(items, demands, capacity, deadline):
    """Best fit by residual capacity, with stable ties."""
    residuals = []
    bins = []
    for node in items:
        if time.perf_counter() >= deadline:
            return None
        weight = float(demands[node])
        pos = bisect.bisect_left(residuals, (weight - EPS, -1))
        if pos == len(residuals):
            index, residual = len(bins), capacity
            bins.append([])
        else:
            residual, index = residuals.pop(pos)
        bins[index].append(node)
        bisect.insort(residuals, (residual - weight, index))
    return bins


def _pack(items, demands, capacity, target, deadline):
    items = sorted(items, key=lambda node: -demands[node])
    for name, method in (("ffd", _pack_first_fit), ("bfd", _pack_best_fit)):
        bins = method(items, demands, capacity, deadline)
        if bins is None or len(bins) <= target:
            return bins, name
    # Small ordering changes address nearly equal demands without changing feasibility.
    trial_deadline = min(deadline, time.perf_counter() + 0.005)
    for trial in range(1, 7):
        if time.perf_counter() >= trial_deadline:
            break
        width = capacity * trial * 0.004
        order = sorted(items, key=lambda node: (-round(demands[node] / width), (node * (31 + trial)) % 997))
        bins = _pack_best_fit(order, demands, capacity, trial_deadline)
        if bins is not None and len(bins) <= target:
            return bins, "bfd_tie_break"
    return None, None


def _two_opt(route, dmat, deadline, max_passes=5):
    route = route[:]
    if len(route) < 3:
        return route
    # Use indexed slices for the inner scan and poll between rows.
    for _ in range(max_passes):
        changed = False
        for i in range(len(route) - 1):
            if time.perf_counter() >= deadline:
                return route
            tail = np.asarray(route[i + 1:] + [0])
            a, b = route[i - 1] if i else 0, route[i]
            deltas = dmat[a, tail[:-1]] + dmat[b, tail[1:]] - dmat[a, b] - dmat[tail[:-1], tail[1:]]
            best = int(deltas.argmin())
            if deltas[best] < -EPS:
                route[i:i + best + 2] = reversed(route[i:i + best + 2])
                changed = True
        if not changed:
            break
    return route


def _route_bins(bins, dmat, deadline):
    routes = []
    for items in bins:
        remaining = np.asarray(items, dtype=np.intp)
        route = []
        last = 0
        while len(remaining):
            if time.perf_counter() >= deadline:
                return None
            pos = int(dmat[last, remaining].argmin())
            last = int(remaining[pos])
            route.append(last)
            remaining = np.delete(remaining, pos)
        routes.append(route)
    # Preserve a complete NN witness even if this short improvement pass truncates.
    for idx, route in enumerate(routes):
        if time.perf_counter() >= deadline:
            break
        routes[idx] = _two_opt(route, dmat, deadline, max_passes=1)
    return routes


def _cluster_packing(bins, dmat, demands, deadline):
    """Rematch equal-demand customers around the heaviest member of each bin."""
    groups = {}
    clustered = []
    for idx, (anchor, *members) in enumerate(bins):
        clustered.append([anchor])
        for node in members:
            slots, customers = groups.setdefault(demands[node], ([], []))
            slots.append(idx)
            customers.append(node)
    for weight in sorted(groups, reverse=True):
        slots, customers = groups[weight]
        pool = np.asarray(customers)
        available = np.ones(len(pool), dtype=bool)
        for idx in slots:
            if time.perf_counter() >= deadline:
                return None
            nodes = np.asarray(clustered[idx])
            distances = dmat[nodes[:, None], pool].min(axis=0)
            chosen = int(np.where(available, distances, np.inf).argmin())
            clustered[idx].append(int(pool[chosen]))
            available[chosen] = False
    return clustered


def _preserve_geometric_routes(cw, bins, demands, capacity, target, deadline):
    """Keep complete CW routes whenever the remaining demands still pack."""
    open_nodes = sorted((node for route in cw for node in route), key=lambda node: -demands[node])
    open_bins = bins
    compact = []
    available_slack = target * capacity - sum(demands[node] for node in open_nodes)
    for route, load in sorted(zip(cw, _loads(cw, demands)), key=lambda pair: -pair[1]):
        if time.perf_counter() >= deadline or len(compact) == target - 1:
            break
        slack = capacity - load
        if slack > available_slack + EPS:
            continue
        removed = set(route)
        remainder = [node for node in open_nodes if node not in removed]
        next_bins = _pack_best_fit(remainder, demands, capacity, deadline)
        if next_bins is None:
            break
        if len(next_bins) > target - len(compact) - 1:
            continue
        compact.append(route)
        open_bins, open_nodes = next_bins, remainder
        available_slack -= slack
    return compact, open_bins


def _cheapest_split(routes, dmat, target_k):
    cuts = sorted(
        (dmat[left, 0] + dmat[0, right] - dmat[left, right], r, i)
        for r, route in enumerate(routes)
        for i, (left, right) in enumerate(zip(route, route[1:]), start=1)
    )
    selected = {(r, i) for _, r, i in cuts[:target_k - len(routes)]}
    result = []
    for r, route in enumerate(routes):
        start = 0
        for i in range(1, len(route)):
            if (r, i) in selected:
                result.append(route[start:i])
                start = i
        result.append(route[start:])
    return result


def _merge_routes(routes, dmat, demands, capacity, target_k, deadline):
    """Tier 1. The least-cost legal join may have negative savings."""
    routes = list(routes)
    loads = _loads(routes, demands)
    while len(routes) > target_k and time.perf_counter() < deadline:
        if sum(sorted(loads)[:2]) > capacity + EPS:
            break
        ends = np.array([(r[0], r[-1]) for r in routes])
        load = np.asarray(loads)
        best = (float("inf"), -1, -1, -1, -1)
        for a, pair in enumerate(ends[:-1]):
            if time.perf_counter() >= deadline:
                return routes
            viable = np.flatnonzero(load[a] + load[a + 1:] <= capacity + EPS) + a + 1
            if not len(viable):
                continue
            right = ends[viable]
            delta = dmat[pair[:, None, None], right] - dmat[pair, 0][:, None, None] - dmat[0, right]
            x, b, y = np.unravel_index(delta.argmin(), delta.shape)
            candidate = (float(delta[x, b, y]), a, int(viable[b]), x, y)
            best = min(best, candidate)
        _, a, b, x, y = best
        if a < 0 or time.perf_counter() >= deadline:
            break
        first = routes[a][::-1] if x == 0 else routes[a]
        second = routes[b][::-1] if y == 1 else routes[b]
        routes[a] = first + second
        routes.pop(b)
        loads[a] += loads.pop(b)
    return routes


def _best_edge(route, node, dmat):
    path = np.asarray([0, *route, 0])
    left, right = path[:-1], path[1:]
    deltas = dmat[left, node] + dmat[node, right] - dmat[left, right]
    pos = int(deltas.argmin())
    return float(deltas[pos]), pos


def _free_capacity(routes, loads, weight, dmat, demands, capacity, deadline):
    """Find a 1-1 swap that creates an insertion slot for the donor item."""
    room = capacity - np.asarray(loads)
    arrays = [np.asarray(r) for r in routes]
    best = None
    for a, left in enumerate(arrays):
        left_path = np.asarray([0, *routes[a], 0])
        left_weight = demands[left][:, None]
        viable = np.flatnonzero(room[a] + room[a + 1:] >= weight - EPS) + a + 1
        for b in viable:
            if time.perf_counter() >= deadline:
                return False
            right = arrays[b]
            diff = left_weight - demands[right]
            room_a, room_b = room[a] + diff, room[b] - diff
            feasible = (np.minimum(room_a, room_b) >= -EPS) & (np.maximum(room_a, room_b) >= weight - EPS)
            if not feasible.any():
                continue
            right_path = np.asarray([0, *routes[b], 0])
            gain = _swap_deltas(left_path, right_path, dmat)
            pos_a, pos_b = np.unravel_index(np.where(feasible, gain, np.inf).argmin(), gain.shape)
            move = (float(gain[pos_a, pos_b]), a, b, pos_a, pos_b, float(diff[pos_a, pos_b]))
            if best is None or move < best:
                best = move
    if best is None or time.perf_counter() >= deadline:
        return False
    _, a, b, pos_a, pos_b, diff = best
    routes[a][pos_a], routes[b][pos_b] = routes[b][pos_b], routes[a][pos_a]
    loads[a] -= diff
    loads[b] += diff
    return True


def _dissolve_donor(routes, donor, dmat, demands, capacity, deadline):
    """Tier 2. Own all edits until every donor item has been placed."""
    workspace = [route[:] for i, route in enumerate(routes) if i != donor]
    loads = _loads(workspace, demands)
    for node in sorted(routes[donor], key=lambda node: -demands[node]):
        weight = float(demands[node])
        for attempt in range(2):
            best = None
            for r, route in enumerate(workspace):
                if time.perf_counter() >= deadline:
                    return None
                if loads[r] + weight <= capacity + EPS:
                    delta, position = _best_edge(route, node, dmat)
                    option = (delta, r, position)
                    if best is None or option < best:
                        best = option
            if best is not None:
                _, r, position = best
                workspace[r].insert(position, node)
                loads[r] += weight
                break
            if attempt or not _free_capacity(workspace, loads, weight, dmat, demands, capacity, deadline):
                return None
    return workspace if time.perf_counter() < deadline else None

def _two_for_one(left, right, free_left, demands, deadline):
    """Concentrate load by moving two small items in exchange for one."""
    left_positions = sorted(range(len(left)), key=lambda i: demands[left[i]])[:32]
    right_positions = sorted(range(len(right)), key=lambda i: -demands[right[i]])[:32]
    for i, a in enumerate(left_positions):
        for b in left_positions[i + 1:]:
            if time.perf_counter() >= deadline:
                return False
            pair_weight = demands[left[a]] + demands[left[b]]
            for c in right_positions:
                shift = demands[right[c]] - pair_weight
                if shift <= EPS:
                    break
                if shift <= free_left + EPS:
                    x, y, z = left[a], left[b], right[c]
                    left[max(a, b)] = z
                    left.pop(min(a, b))
                    right[c:c + 1] = [x, y]
                    return True
    return False


def _exchange_dissolve(routes, dmat, demands, capacity, deadline):
    """Use disjoint 2-1 exchanges, then attempt a complete donor dissolution."""
    workspace = [route[:] for route in routes]
    room = [capacity - load for load in _loads(routes, demands)]
    available = set(range(len(routes)))
    changed = []
    for a, left in enumerate(workspace):
        if time.perf_counter() >= deadline:
            return None
        if a not in available or len(left) < 2:
            continue
        for b in sorted(available - {a}, key=lambda r: (-room[r], r)):
            if time.perf_counter() >= deadline:
                return None
            if _two_for_one(left, workspace[b], room[a], demands, deadline):
                changed.append(b)
                available.difference_update((a, b))
                break
    for donor in sorted(changed, key=lambda r: sum(demands[node] for node in workspace[r]))[:4]:
        if time.perf_counter() >= deadline:
            return None
        result = _dissolve_donor(workspace, donor, dmat, demands, capacity, deadline)
        if result is not None:
            # Swaps were performed for capacity, so reconstruct their route order.
            return _route_bins(result, dmat, deadline)
    return None


def _repack_routes(routes, dmat, demands, capacity, target_k, deadline):
    """Tier 3. Repack small neighborhoods and try a bounded exchange transaction."""
    routes = list(routes)
    while len(routes) > target_k and time.perf_counter() < deadline:
        loads = _loads(routes, demands)
        ends = np.asarray([(route[0], route[-1]) for route in routes])
        donors = sorted(range(len(routes)), key=loads.__getitem__)[:8]
        candidate = None
        for donor in donors:
            if time.perf_counter() >= deadline:
                return routes
            neighbors = [i for i in range(len(routes)) if i != donor]
            distances = dmat[ends[donor, :, None, None], ends].min(axis=(0, 2))
            by_distance = sorted(neighbors, key=lambda r: (distances[r], loads[r]))
            by_load = sorted(neighbors, key=lambda r: (loads[r], distances[r]))
            for order in (by_distance, by_load):
                group = [donor]
                load = loads[donor]
                for other in order[:7]:
                    if time.perf_counter() >= deadline:
                        return routes
                    group.append(other)
                    load += loads[other]
                    target = len(group) - 1
                    if load > target * capacity + EPS:
                        continue
                    items = sorted((c for r in group for c in routes[r]), key=lambda c: -demands[c])
                    bins = _pack_best_fit(items, demands, capacity, deadline)
                    if bins is None:
                        return routes
                    if len(bins) <= target:
                        replacement = _route_bins(bins, dmat, deadline)
                        if replacement is not None and time.perf_counter() < deadline:
                            remaining = [r for idx, r in enumerate(routes) if idx not in group]
                            candidate = remaining + _cheapest_split(replacement, dmat, target)
                        break
                if candidate is not None:
                    break
            if candidate is not None:
                break
        if candidate is None:
            candidate = _exchange_dissolve(routes, dmat, demands, capacity, deadline)
        if candidate is None or time.perf_counter() >= deadline:
            break
        routes = candidate
    return routes


def _swap_deltas(left, right, dmat):
    a, b = left[1:-1][:, None], right[1:-1]
    pa, na = left[:-2, None], left[2:, None]
    pb, nb = right[:-2], right[2:]
    return (
        dmat[pa, b] + dmat[b, na] - dmat[pa, a] - dmat[a, na]
        + dmat[pb, a] + dmat[a, nb] - dmat[pb, b] - dmat[b, nb]
    )


def _relocate_deltas(left, right, dmat):
    node = left[1:-1, None]
    prev, following = left[:-2, None], left[2:, None]
    x, y = right[:-1], right[1:]
    return (
        dmat[prev, following] - dmat[prev, node] - dmat[node, following]
        + dmat[x, node] + dmat[node, y] - dmat[x, y]
    )


def _exchange_tails(left, right, dmat, demands, capacity, deadline):
    """Select a capacity-feasible 2-opt* move across either route orientation."""
    load_left = np.cumsum(demands[left[:-1]])[:, None]
    left_a, left_b = left[:-1, None], left[1:, None]
    best = (0.0, 0, 0, False)
    for reverse in (False, True):
        if time.perf_counter() >= deadline:
            return best
        oriented = right[::-1] if reverse else right
        load_right = np.cumsum(demands[oriented[:-1]])
        new_left = load_left + load_right[-1] - load_right
        new_right = load_left[-1, 0] + load_right - load_left
        feasible = np.maximum(new_left, new_right) <= capacity + EPS
        feasible[0, -1] = False
        feasible[-1, 0] = False
        right_a, right_b = oriented[:-1], oriented[1:]
        delta = dmat[left_a, right_b] + dmat[right_a, left_b] - dmat[left_a, left_b] - dmat[right_a, right_b]
        i, j = np.unravel_index(np.where(feasible, delta, np.inf).argmin(), delta.shape)
        best = min(best, (float(delta[i, j]), int(i), int(j), reverse))
    return best


def _polish_pair(routes, loads, a, b, dmat, demands, capacity, deadline):
    left, right = (np.asarray([0, *routes[r], 0]) for r in (a, b))
    if len(left) * len(right) > 32768 or time.perf_counter() >= deadline:
        return False
    wa, wb = demands[left[1:-1]], demands[right[1:-1]]
    diff = wa[:, None] - wb
    feasible = (loads[a] - diff <= capacity + EPS) & (loads[b] + diff <= capacity + EPS)
    swap = np.where(feasible, _swap_deltas(left, right, dmat), np.inf)
    x, y = np.unravel_index(swap.argmin(), swap.shape)
    best = (float(swap[x, y]), a, b, int(x), int(y), True)
    for src, dst, src_path, dst_path, weights in ((a, b, left, right, wa), (b, a, right, left, wb)):
        if len(routes[src]) == 1 or not np.any(loads[dst] + weights <= capacity + EPS):
            continue
        if time.perf_counter() >= deadline:
            return False
        feasible = loads[dst] + weights[:, None] <= capacity + EPS
        delta = np.where(feasible, _relocate_deltas(src_path, dst_path, dmat), np.inf)
        x, y = np.unravel_index(delta.argmin(), delta.shape)
        best = min(best, (float(delta[x, y]), src, dst, int(x), int(y), False))
    delta, src, dst, x, y, swap_nodes = best
    if delta >= -EPS and time.perf_counter() < deadline:
        delta, x, y, reverse = _exchange_tails(left, right, dmat, demands, capacity, deadline)
        if delta < -EPS and time.perf_counter() < deadline:
            left_route = routes[a]
            right_route = routes[b][::-1] if reverse else routes[b]
            routes[a] = _two_opt(left_route[:x] + right_route[y:], dmat, deadline, max_passes=2)
            routes[b] = _two_opt(right_route[:y] + left_route[x:], dmat, deadline, max_passes=2)
            loads[a], loads[b] = _loads((routes[a], routes[b]), demands)
            return True
        return False
    if delta >= -EPS or time.perf_counter() >= deadline:
        return False
    source, destination = routes[src], routes[dst]
    weight = float(demands[source[x]])
    if swap_nodes:
        weight -= float(demands[destination[y]])
        source[x], destination[y] = destination[y], source[x]
    else:
        destination.insert(y, source.pop(x))
    loads[src] -= weight
    loads[dst] += weight
    routes[src] = _two_opt(source, dmat, deadline, max_passes=2)
    routes[dst] = _two_opt(destination, dmat, deadline, max_passes=2)
    return True


def _polish_exact(routes, dmat, demands, capacity, deadline):
    """Keep the route count and commit only improving moves."""
    routes = [route[:] for route in routes]
    loads = _loads(routes, demands)
    for i, route in enumerate(routes):
        if time.perf_counter() >= deadline:
            return routes
        routes[i] = _two_opt(route, dmat, deadline)
    count = len(routes)
    for _ in range(20):
        changed = False
        start = np.asarray([route[0] for route in routes])
        end = np.asarray([route[-1] for route in routes])
        visited = set()
        for a in range(count):
            if time.perf_counter() >= deadline:
                return routes
            if count <= 25:
                neighbors = range(a + 1, count)
            else:
                distance = np.minimum.reduce((
                    dmat[start[a], start], dmat[start[a], end], dmat[end[a], start], dmat[end[a], end],
                ))
                neighbors = np.argsort(distance, kind="stable")[:13]
            for b in neighbors:
                if time.perf_counter() >= deadline:
                    return routes
                pair = (min(a, b), max(a, b))
                if a == b or pair in visited:
                    continue
                visited.add(pair)
                changed |= _polish_pair(routes, loads, a, b, dmat, demands, capacity, deadline)
        if not changed:
            break
    return routes


def _obstructions(routes, dmat, demands, capacity, deadline):
    loads = np.asarray(_loads(routes, demands))
    if not len(loads) or time.perf_counter() >= deadline:
        return {}
    donor = int(loads.argmin())
    residual = max((capacity - load for r, load in enumerate(loads) if r != donor), default=-np.inf)
    min_item = min(float(demands[node]) for node in routes[donor])
    load_pairs = int(sum(
        np.count_nonzero(load + loads[r + 1:] <= capacity + EPS) for r, load in enumerate(loads)
    ))
    positive_pairs = 0
    ends = np.asarray([(route[0], route[-1]) if len(route) > 1 else (route[0], 0) for route in routes])
    for a, left in enumerate(ends[:-1]):
        if time.perf_counter() >= deadline:
            return {}
        right = ends[a + 1:]
        savings = dmat[0, left][:, None, None] + dmat[0, right] - dmat[left[:, None, None], right]
        positive_pairs += int(np.count_nonzero(
            (savings > EPS) & (left[:, None, None] > 0) & (right > 0)
            & ((loads[a] + loads[a + 1:] <= capacity + EPS)[None, :, None])
        ))
    return dict(load_feasible_pairs=load_pairs, positive_savings_pairs=positive_pairs,
                min_donor_item=min_item, min_donor_item_insertable=bool(min_item <= residual + EPS))


def _target_status(target, size, total, capacity):
    if target is None:
        return None, "missing"
    if isinstance(target, bool) or not isinstance(target, numbers.Real) or not np.isfinite(target):
        return None, "invalid"
    if int(target) != target or target < 1:
        return None, "invalid"
    if target > size or total > target * capacity + EPS:
        return None, "infeasible"
    return int(target), "eligible"


def run_cvrp_fleet_aware_exact_k_v1(
    distance_matrix, demands, capacity, hook_fn, *, postprocess_mode="none", time_budget_ms=500.0,
    template_options=None, capture_merge_sequence=False, record_incumbent=None, target_k=None,
):
    """Return the best exact fleet found, with a complete free-fleet fallback."""
    started = time.perf_counter()
    hard_deadline = float("inf") if time_budget_ms is None else started + time_budget_ms / 1000
    margin_ms = 0.0 if time_budget_ms is None else max(6.0, min(15.0, 0.015 * time_budget_ms))
    deadline = hard_deadline - margin_ms / 1000
    if postprocess_mode not in ALLOWED_POSTPROCESS_MODES:
        raise ValueError(f"unsupported_postprocess_mode:{postprocess_mode}")
    opts = template_options or {}
    repair_enabled = bool(opts.get("fleet_repair_enabled", True))
    dmat = distance_matrix
    total = float(np.sum(demands))
    target, target_status = _target_status(target_k, len(demands) - 1, total, capacity)
    rho = total / (target * capacity) if target is not None else 0.0
    if isinstance(hook_fn, Mapping):
        static, adjustment = hook_fn[_STATIC.name], hook_fn[_ADJUSTMENT.name]
    else:
        static, adjustment = hook_fn

    # Reserve time for the witness and repair when targeting an exact fleet.
    construct_until = deadline
    if target is not None and repair_enabled and time_budget_ms is not None:
        construct_until = min(deadline, started + 0.60 * time_budget_ms / 1000)
    cw, sequence, diag, timing = _construct(
        dmat, demands, capacity, static, adjustment, target, rho, construct_until, capture_merge_sequence,
    )
    cw_cost = _cost(cw, dmat)
    best_free_routes = cw
    best_exact_routes = cw[:] if len(cw) == target else None
    exact_cost = cw_cost if best_exact_routes is not None else float("inf")
    exact_source = "cw" if best_exact_routes is not None else None
    if record_incumbent is not None:
        record_incumbent(cw, cw_cost, stable_routes=True)

    def consider_exact(routes, source):
        nonlocal best_exact_routes, exact_cost, exact_source
        if routes is not None and len(routes) == target:
            cost = _cost(routes, dmat)
            if record_incumbent is not None:
                record_incumbent(routes, cost, stable_routes=True)
            if cost < exact_cost:
                best_exact_routes, exact_cost, exact_source = routes, cost, source

    witness = None
    packing = None
    repair_counts = dict(tier1=0, tier2=0, tier3=0, tier4=0)
    repaired = cw
    post_started = time.perf_counter()
    if target is not None and repair_enabled and post_started < deadline:
        pack_until = min(deadline, post_started + 0.045)
        if best_exact_routes is not None:
            pack_until = min(pack_until, deadline - 0.010)
        if pack_until > post_started:
            bins, packing = _pack([c for route in cw for c in route], demands, capacity, target, pack_until)
            if bins is not None:
                witness = _route_bins(bins, dmat, pack_until)
                if witness is not None:
                    witness = _cheapest_split(witness, dmat, target) if len(witness) < target else witness
                    consider_exact(witness, "ffd_witness")
                    if len(cw) != target:
                        clustered = _cluster_packing(bins, dmat, demands, pack_until)
                        clustered = _route_bins(clustered, dmat, pack_until) if clustered is not None else None
                        if clustered is not None:
                            clustered = _cheapest_split(clustered, dmat, target) if len(clustered) < target else clustered
                            if _cost(clustered, dmat) < _cost(witness, dmat):
                                witness = clustered
                                consider_exact(witness, "ffd_witness")
                    if len(cw) > target and rho >= 0.94 and len(cw) < 2 * target:
                        now = time.perf_counter()
                        preserve_until = min(deadline, now + 0.18 * (deadline - now))
                        compact, open_bins = _preserve_geometric_routes(
                            cw, bins, demands, capacity, target, preserve_until,
                        )
                        geometry_until = min(deadline, preserve_until + 0.018)
                        if compact:
                            open_bins = _cluster_packing(open_bins, dmat, demands, geometry_until) or open_bins
                            remaining = _route_bins(open_bins, dmat, geometry_until)
                            if remaining is not None:
                                geometry = _cheapest_split(compact + remaining, dmat, target)
                                if _cost(geometry, dmat) < _cost(witness, dmat):
                                    witness = geometry
                                    consider_exact(witness, "ffd_witness")
        # Keep time for polishing each viable exact-fleet construction.
        repair_until = deadline
        if best_exact_routes is not None:
            repair_until = min(deadline, time.perf_counter() + min(0.030, (deadline - time.perf_counter()) / 5))
        elif time_budget_ms is not None and postprocess_mode != "none":
            repair_until -= min(0.140, time_budget_ms * 0.20 / 1000)
        if len(repaired) > target and time.perf_counter() < repair_until:
            repaired = _merge_routes(repaired, dmat, demands, capacity, target, repair_until)
            repair_counts["tier1"] = len(cw) - len(repaired)
            tier2_until = min(repair_until, time.perf_counter() + max(0.0, repair_until - time.perf_counter()) * 0.5)
            while len(repaired) > target and time.perf_counter() < tier2_until:
                loads = _loads(repaired, demands)
                donors = sorted(range(len(repaired)), key=loads.__getitem__)[:4]
                next_routes = None
                for donor in donors:
                    next_routes = _dissolve_donor(repaired, donor, dmat, demands, capacity, tier2_until)
                    if next_routes is not None:
                        break
                if next_routes is None:
                    break
                repaired = next_routes
                repair_counts["tier2"] += 1
            if len(repaired) > target:
                before = len(repaired)
                repaired = _repack_routes(repaired, dmat, demands, capacity, target, repair_until)
                repair_counts["tier3"] = before - len(repaired)
        elif len(repaired) < target and time.perf_counter() < repair_until:
            repair_counts["tier4"] = target - len(repaired)
            repaired = _cheapest_split(repaired, dmat, target)
        if repaired is not cw:
            consider_exact(repaired, "repair")

    if best_exact_routes is not None and (repair_enabled or postprocess_mode != "none"):
        candidates = [(repaired, "cw" if repaired is cw else "repair"), (witness, "ffd_witness")]
        candidates = [(routes, source) for routes, source in candidates if routes is not None and len(routes) == target]
        candidates.sort(key=lambda item: item[1] == exact_source)
        for idx, (routes, source) in enumerate(candidates):
            now = time.perf_counter()
            if now >= deadline:
                break
            polish_until = now + (deadline - now) * 0.3 if len(candidates) > idx + 1 else deadline
            consider_exact(_polish_exact(routes, dmat, demands, capacity, polish_until), source)
    elif target is not None and not repair_enabled and postprocess_mode != "none" and time.perf_counter() < deadline:
        best_free_routes = _polish_exact(cw, dmat, demands, capacity, deadline)
    elif best_exact_routes is None and postprocess_mode == "relocate_2opt" and time.perf_counter() < deadline:
        best_free_routes, _ = apply_relocate_2opt_guarded(
            cw, dmat, demands, capacity, deadline=None if time_budget_ms is None else deadline,
            safety_margin_ms=0.0,
        )
        if record_incumbent is not None:
            record_incumbent(best_free_routes, _cost([r[1:-1] for r in best_free_routes], dmat), stable_routes=True)
        if len(best_free_routes) == target:
            consider_exact([route[1:-1] for route in best_free_routes], "cw")
    elif best_exact_routes is None and postprocess_mode == "intra_2opt":
        best_free_routes = [_two_opt(route, dmat, deadline) for route in cw]

    if capture_merge_sequence or time.perf_counter() + 0.006 < deadline:
        diag.update(_obstructions(cw, dmat, demands, capacity, deadline))
    diag.update(
        target_k_status=target_status, target_k=target, rho=rho, fleet_repair_enabled=repair_enabled,
        pre_repair_route_count=len(cw), pre_repair_cost=cw_cost, pre_repair_exact_k=len(cw) == target,
        exact_source=exact_source, ffd_witness=witness is not None, witness_packing=packing,
        repair_moves=repair_counts,
    )
    routes = best_exact_routes if best_exact_routes is not None else best_free_routes
    routes = [[0, *route, 0] if route[0] else route for route in routes]
    ended = time.perf_counter()
    anytime = ended >= deadline
    meta = dict(
        **timing, candidate_pair_count=diag["static_positive_savings_pairs"], postprocess_mode=postprocess_mode,
        postprocess_ms=(ended - post_started) * 1000, budget_exhausted=False,
        stop_reason="anytime_safety_exit" if anytime else "completed",
        voluntary_anytime_return=anytime, local_search_truncated=anytime,
        return_margin_ms=(hard_deadline - ended) * 1000 if time_budget_ms is not None else None,
        fleet_diagnostics=diag,
    )
    if capture_merge_sequence:
        meta.update(merge_sequence=sequence, pre_postprocess_routes=[[0, *route, 0] for route in cw])
    return routes, meta


register_template(TemplateSpec(
    template_id=FLEET_EXACT_K_TEMPLATE_KEY[0],
    template_version=FLEET_EXACT_K_TEMPLATE_KEY[1],
    problem_family="cvrp",
    paradigm="parallel_merge",
    hook_name=_STATIC.name,
    hook_signature=_STATIC.signature,
    allowed_postprocess_modes=ALLOWED_POSTPROCESS_MODES,
    runner=run_cvrp_fleet_aware_exact_k_v1,
    default_task_description=(
        "Score positive-savings CVRP merges with two independent NumPy hooks. "
        "The static hook scores aligned one-based endpoint pairs using a symmetric distance matrix, "
        "a demand vector with a zero depot, and positive capacity. Higher scores rank earlier. "
        "The adjustment hook returns one finite additive score per pair in a block of up to 64 feasible endpoints. "
        "Its base rank decreases from one to zero within the block. Savings are divided by the maximum positive saving. "
        "Route loads, residual capacity and endpoint demands are fractions of capacity. "
        "Target fleet, current route count and total demand divided by target fleet capacity are scalars. "
        "The seven aligned vectors are read-only. Zero adjustment preserves the static order. "
        "The runner refreshes state each block and stops merging at the target."
    ),
    default_template_program=_BASELINE_PROGRAM,
    default_baseline_hook_code=CLASSIC_CW_STATIC_HOOK_CODE,
    template_source_sha256=compute_template_source_sha256(
        run_cvrp_fleet_aware_exact_k_v1, _construct, _read_only, _scores, _cost, _loads,
        _pack, _pack_first_fit, _pack_best_fit, _route_bins, _cluster_packing, _preserve_geometric_routes,
        _two_opt, _cheapest_split,
        _merge_routes, _best_edge, _free_capacity, _dissolve_donor, _repack_routes, _exchange_dissolve,
        _two_for_one, _polish_exact, _polish_pair, _swap_deltas, _relocate_deltas, _exchange_tails,
        _target_status, _obstructions,
        apply_relocate_2opt_guarded, _find_relocate_destination_guarded, _two_opt_single_route_guarded,
        _effective_solve_deadline,
    ),
    protocol_id=LEGACY_CVRP_PROTOCOL_ID,
    hook_specs=(_STATIC, _ADJUSTMENT),
    baseline_hook_implementations={
        _STATIC.name: CLASSIC_CW_STATIC_HOOK_CODE, _ADJUSTMENT.name: BASELINE_ADJUSTMENT_CODE,
    },
))


