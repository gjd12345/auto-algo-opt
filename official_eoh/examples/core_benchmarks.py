"""TSPLIB/CVRPLIB Core 实例解析与结构化 held-out 评测。"""
from __future__ import annotations
import math
import re
from pathlib import Path
import numpy as np

def _header(lines: list[str], key: str, default: str = "") -> str:
    for line in lines:
        match = re.match(rf"^{re.escape(key)}\s*:?\s*(.+)$", line.strip(), re.I)
        if match:
            return match.group(1).strip()
    return default

def load_tsp(path: str | Path) -> dict:
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip().upper() == "NODE_COORD_SECTION") + 1
    coords = []
    for line in lines[start:]:
        if line.strip().upper() == "EOF": break
        parts = line.split()
        if len(parts) >= 3: coords.append((float(parts[1]), float(parts[2])))
    optimum = _header(lines, "BEST_KNOWN") or _header(lines, "OPTIMUM")
    return {"name": _header(lines, "NAME", Path(path).stem), "coords": np.asarray(coords), "optimum": float(optimum) if optimum else None}

def evaluate_tsp(heuristic, instance: dict) -> dict:
    coords = instance["coords"]; n = len(coords)
    dist = np.linalg.norm(coords[:, None, :] - coords[None, :, :], axis=2)
    route = [0]
    while len(route) < n:
        unvisited = np.asarray([node for node in range(n) if node not in route], dtype=int)
        nxt = int(heuristic(route[-1], 0, unvisited, dist.copy()))
        if nxt not in unvisited: raise ValueError("heuristic returned visited or unknown node")
        route.append(nxt)
    cost = float(sum(dist[a, b] for a, b in zip(route, route[1:] + route[:1])))
    optimum = instance.get("optimum")
    return {"instance": instance["name"], "nodes": n, "feasible": True, "tour_cost": cost, "optimum": optimum, "relative_gap_pct": ((cost - optimum) / optimum * 100.0) if optimum else None}

def load_cvrp(path: str | Path) -> dict:
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    def section(name: str, stop: set[str]) -> list[list[str]]:
        start = next(i for i, line in enumerate(lines) if line.strip().upper() == name) + 1
        rows = []
        for line in lines[start:]:
            if line.strip().upper() in stop: break
            if line.split(): rows.append(line.split())
        return rows
    coords_rows = section("NODE_COORD_SECTION", {"DEMAND_SECTION"})
    demand_rows = section("DEMAND_SECTION", {"DEPOT_SECTION"})
    coords = np.asarray([(float(row[1]), float(row[2])) for row in coords_rows])
    demands = np.zeros(len(coords), dtype=int)
    for row in demand_rows: demands[int(row[0]) - 1] = int(row[1])
    optimum = _header(lines, "BEST_KNOWN") or _header(lines, "OPTIMUM")
    return {"name": _header(lines, "NAME", Path(path).stem), "coords": coords, "demands": demands, "capacity": int(_header(lines, "CAPACITY")), "optimum": float(optimum) if optimum else None}

def evaluate_cvrp(heuristic, instance: dict) -> dict:
    coords=instance["coords"]; demands=instance["demands"]; cap=instance["capacity"]; n=len(coords)
    dist=np.linalg.norm(coords[:,None,:]-coords[None,:,:],axis=2); route=[0]; unvisited=set(range(1,n)); load=0
    while unvisited:
        feasible=np.asarray(sorted(node for node in unvisited if load + demands[node] <= cap), dtype=int)
        if len(feasible)==0: route.append(0); load=0; continue
        nxt=int(heuristic(route[-1],0,feasible,float(cap-load),demands.copy(),dist.copy()))
        if nxt == 0: route.append(0); load=0; continue
        if nxt not in feasible: raise ValueError("heuristic returned infeasible customer")
        route.append(nxt); load += int(demands[nxt]); unvisited.remove(nxt)
    if route[-1] != 0: route.append(0)
    cost=float(sum(dist[a,b] for a,b in zip(route,route[1:]))); optimum=instance.get("optimum")
    return {"instance":instance["name"],"customers":n-1,"feasible":True,"capacity_valid":True,"coverage_valid":True,"route_cost":cost,"optimum":optimum,"relative_gap_pct":((cost-optimum)/optimum*100.0) if optimum else None}
