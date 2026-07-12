"""TSPLIB/CVRPLIB Core 实例解析与结构化 held-out 评测。"""
from __future__ import annotations
import math
import re
from pathlib import Path
import numpy as np

TSP_OPTIMA = {"eil51":426,"st70":675,"kroA100":21282,"ch130":6110,"kroA200":29368,"tsp225":3916,"a280":2579,"pcb442":50778,"rat575":6773,"rat783":8806,"pr1002":259045,"pcb3038":137694}
CVRP_OPTIMA = {"X-n101-k25":27591,"X-n129-k18":28940,"X-n153-k22":21220,"X-n200-k36":58578,"X-n251-k28":38684,"X-n303-k21":21736,"X-n351-k40":25896,"X-n401-k29":66154,"X-n502-k39":26524,"X-n1001-k43":72355}

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
    name = _header(lines, "NAME", Path(path).stem)
    optimum = _header(lines, "BEST_KNOWN") or _header(lines, "OPTIMUM")
    return {"name": name, "coords": np.asarray(coords), "optimum": float(optimum) if optimum else TSP_OPTIMA.get(name)}

def evaluate_tsp(heuristic, instance: dict) -> dict:
    coords = instance["coords"]; n = len(coords)
    # TSPLIB EUC_2D 使用最近整数距离，不使用连续欧氏距离。
    dist = np.rint(np.linalg.norm(coords[:, None, :] - coords[None, :, :], axis=2))
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
    name = _header(lines, "NAME", Path(path).stem)
    optimum = _header(lines, "BEST_KNOWN") or _header(lines, "OPTIMUM")
    return {"name": name, "coords": coords, "demands": demands, "capacity": int(_header(lines, "CAPACITY")), "optimum": float(optimum) if optimum else CVRP_OPTIMA.get(name)}

def evaluate_cvrp(heuristic, instance: dict) -> dict:
    coords=instance["coords"]; demands=instance["demands"]; cap=instance["capacity"]; n=len(coords)
    dist=np.rint(np.linalg.norm(coords[:,None,:]-coords[None,:,:],axis=2)); route=[0]; unvisited=set(range(1,n)); load=0
    steps = 0
    while unvisited:
        steps += 1
        if steps > n * n:
            raise ValueError("heuristic failed to make routing progress")
        feasible=np.asarray(sorted(node for node in unvisited if load + demands[node] <= cap), dtype=int)
        if len(feasible)==0: route.append(0); load=0; continue
        nxt=int(heuristic(route[-1],0,feasible,float(cap-load),demands.copy(),dist.copy()))
        if nxt == 0: route.append(0); load=0; continue
        if nxt not in feasible: raise ValueError("heuristic returned infeasible customer")
        route.append(nxt); load += int(demands[nxt]); unvisited.remove(nxt)
    if route[-1] != 0: route.append(0)
    cost=float(sum(dist[a,b] for a,b in zip(route,route[1:]))); optimum=instance.get("optimum")
    return {"instance":instance["name"],"customers":n-1,"feasible":True,"capacity_valid":True,"coverage_valid":True,"route_cost":cost,"optimum":optimum,"relative_gap_pct":((cost-optimum)/optimum*100.0) if optimum else None}
