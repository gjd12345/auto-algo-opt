import importlib
import json
import os
import re
import sys
import time

import numpy as np
import requests

src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
example_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if src_path not in sys.path:
    sys.path.insert(0, src_path)
if example_root not in sys.path:
    sys.path.insert(0, example_root)

from eoh import EVOL
from eoh.utils.getParas import Paras

import prob_insertships_go


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
_last_evolution_instance = None
_V2_DIR = os.path.abspath(os.path.dirname(__file__))


def _load_json(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _find_user_cvrp_config(start_dir: str) -> str | None:
    cur = os.path.abspath(start_dir)
    for _ in range(12):
        candidate = os.path.join(cur, "user_cvrp_hgs", "v2_agent", "config.json")
        if os.path.exists(candidate):
            return candidate
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


def load_config() -> dict:
    cfg = _load_json(CONFIG_PATH)
    if cfg:
        return cfg
    alt = _find_user_cvrp_config(os.path.dirname(example_root))
    if alt:
        return _load_json(alt)
    return {}

def _get_key(env_name: str, config: dict, config_key: str) -> str:
    return os.environ.get(env_name) or config.get(config_key, "") or ""

def _read_text(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def _write_text(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def read_plan() -> str:
    return _read_text(os.path.join(_V2_DIR, "PLAN.md"))

def update_plan(content: str) -> str:
    _write_text(os.path.join(_V2_DIR, "PLAN.md"), content)
    return "OK"

def read_memory() -> str:
    return _read_text(os.path.join(_V2_DIR, "MEMORY.md"))

def update_memory(content: str) -> str:
    _write_text(os.path.join(_V2_DIR, "MEMORY.md"), content)
    return "OK"

def read_research_notes() -> str:
    return _read_text(os.path.join(_V2_DIR, "research_notes.md"))

def _baseline_path() -> str:
    return os.path.abspath(os.path.join(example_root, "..", "..", "..", "..", "..", "Archive_extracted", "final_result.txt"))

def _parse_baseline(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if "," not in line:
                continue
            name, cost = line.split(",", 1)
            try:
                out[name.strip()] = float(cost.strip())
            except Exception:
                continue
    return out


def analyze_latest_results() -> dict:
    global _last_evolution_instance
    if _last_evolution_instance:
        problem = _last_evolution_instance.paras.problem
        output_base = _last_evolution_instance.paras.exp_output_path
    else:
        problem = prob_insertships_go.Evaluation(max_instances=1)
        output_base = os.path.join(example_root, "results_insertships_v2")

    stats = {
        "gen": 0,
        "best_fitness": float("inf"),
        "avg_fitness": 0.0,
        "none_rate": 0.0,
        "last_error": getattr(problem, "_last_error", "None"),
        "last_traceback": getattr(problem, "_last_traceback", "N/A"),
        "best_code": "",
    }

    pops_dir = os.path.join(output_base, "results", "pops")
    if not os.path.isdir(pops_dir):
        return stats

    pop_files = []
    for fn in os.listdir(pops_dir):
        m = re.match(r"population_generation_(\d+)\.json$", fn)
        if m:
            pop_files.append((int(m.group(1)), os.path.join(pops_dir, fn)))
    if not pop_files:
        return stats

    pop_files.sort(key=lambda x: x[0])
    gen_id, pop_path = pop_files[-1]
    with open(pop_path, "r", encoding="utf-8") as f:
        population = json.load(f)

    if not isinstance(population, list) or not population:
        return stats

    objs = [ind.get("objective") for ind in population]
    valid = [o for o in objs if o is not None]
    stats["gen"] = gen_id
    stats["none_rate"] = (len(objs) - len(valid)) / max(len(objs), 1)
    if valid:
        stats["best_fitness"] = float(min(valid))
        stats["avg_fitness"] = float(np.mean(valid))
        best_ind = None
        for ind in population:
            if ind.get("objective") is not None and float(ind["objective"]) == stats["best_fitness"]:
                best_ind = ind
                break
        if best_ind is None:
            best_ind = min([ind for ind in population if ind.get("objective") is not None], key=lambda x: float(x["objective"]))
        stats["best_code"] = best_ind.get("code", "") or ""

    return stats


def run_evolution(
    generations: int = 1,
    sim_time_multi: int = 10,
    max_instances: int = 1,
    seed_path: str | None = None,
    pop_size: int = 4,
    run_timeout_s: int = 60,
    eva_timeout: int = 120,
    objective_use_composite: bool = True,
    objective_res_weight: float = 0.2,
    dataset_density: str = "d25",
    sim_time_interval: int = 1,
    arrival_scale: float = 1.0,
    use_density_source_dirs: bool = False,
    output_dir: str = "",
) -> str:
    global _last_evolution_instance

    config = load_config()
    deepseek_api_key = _get_key("DEEPSEEK_API_KEY", config, "deepseek_api_key")

    importlib.reload(prob_insertships_go)
    os.environ["EOH_OBJECTIVE_USE_COMPOSITE"] = "1" if bool(objective_use_composite) else "0"
    os.environ["EOH_RES_WEIGHT"] = str(float(objective_res_weight))
    os.environ["EOH_RUN_TIMEOUT_S"] = str(int(run_timeout_s))
    problem_instance = prob_insertships_go.Evaluation(
        sim_time_multi=int(sim_time_multi),
        max_instances=int(max_instances),
        run_timeout_s=int(run_timeout_s),
        dataset_density=dataset_density,
        sim_time_interval=int(sim_time_interval),
        arrival_scale=float(arrival_scale),
        use_density_source_dirs=bool(use_density_source_dirs),
    )

    paras = Paras()
    paras.exp_output_path = os.path.join(example_root, "results_insertships_v2")
    if output_dir:
        paras.exp_output_path = os.path.abspath(output_dir)

    if seed_path and os.path.exists(seed_path):
        seed = os.path.abspath(seed_path)
    else:
        seed = os.path.abspath(os.path.join(example_root, "seeds_insertships_go.json"))

    paras.set_paras(
        method="eoh",
        problem=problem_instance,
        llm_api_endpoint="api.deepseek.com",
        llm_api_key=deepseek_api_key,
        llm_model="deepseek-v4-pro",
        ec_pop_size=int(pop_size),
        ec_n_pop=int(generations),
        ec_operators=["m1", "m2"],
        exp_n_proc=4,
        exp_use_seed=True,
        exp_seed_path=seed,
        eva_timeout=int(eva_timeout),
        eva_numba_decorator=False,
    )

    evolution = EVOL(paras)
    _last_evolution_instance = evolution
    evolution.run()
    stats = analyze_latest_results()
    return json.dumps(stats, ensure_ascii=False)

def web_search(query: str) -> str:
    config = load_config()
    tavily_api_key = _get_key("TAVILY_API_KEY", config, "tavily_api_key")
    if not tavily_api_key:
        return "Web search unavailable: No Tavily API key found."

    url = "https://api.tavily.com/search"
    payload = {"api_key": tavily_api_key, "query": query, "search_depth": "advanced", "max_results": 5}
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results:
        return "No search results found."

    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    notes_path = os.path.join(os.path.dirname(__file__), "research_notes.md")
    md = f"\n## Research: {query}\n*Timestamp: {ts}*\n\n"
    summary = []
    for i, r in enumerate(results, start=1):
        title = r.get("title", "No Title")
        link = r.get("url", "#")
        content = r.get("content", "")
        md += f"### {i}. [{title}]({link})\n{content}\n\n"
        summary.append(f"{i}. {title} ({link})")
    with open(notes_path, "a", encoding="utf-8") as f:
        f.write(md)
        f.write("\n---\n")

    return "Saved to research_notes.md\n" + "\n".join(summary)

def _load_seed_code(seed_path: str, seed_index: int = 0) -> str:
    if not os.path.exists(seed_path):
        raise FileNotFoundError(seed_path)
    with open(seed_path, "r", encoding="utf-8") as f:
        seeds = json.load(f)
    if not isinstance(seeds, list) or not seeds:
        raise ValueError("seed file empty or invalid")
    idx = int(seed_index)
    if idx < 0 or idx >= len(seeds):
        raise IndexError("seed_index out of range")
    code = seeds[idx].get("code", "")
    if not code:
        raise ValueError("seed has no code")
    return code

def run_code_review(
    code: str = "",
    candidate_code: str = "",
    seed_path: str = "",
    seed_index: int = 0,
    sim_time_multi: int = 10,
    max_instances: int = 1,
    run_timeout_s: int = 60,
    objective_use_composite: bool = True,
    objective_res_weight: float = 0.2,
    dataset_density: str = "d25",
    sim_time_interval: int = 1,
    arrival_scale: float = 1.0,
    use_density_source_dirs: bool = False,
) -> str:
    if not code and candidate_code:
        code = candidate_code
    if not code and seed_path:
        code = _load_seed_code(seed_path, seed_index=seed_index)
    if not code:
        return "FAILED\nNo code provided."
    os.environ["EOH_OBJECTIVE_USE_COMPOSITE"] = "1" if bool(objective_use_composite) else "0"
    os.environ["EOH_RES_WEIGHT"] = str(float(objective_res_weight))
    os.environ["EOH_RUN_TIMEOUT_S"] = str(int(run_timeout_s))
    eva = prob_insertships_go.Evaluation(
        sim_time_multi=int(sim_time_multi),
        max_instances=int(max_instances),
        run_timeout_s=int(run_timeout_s),
        dataset_density=dataset_density,
        sim_time_interval=int(sim_time_interval),
        arrival_scale=float(arrival_scale),
        use_density_source_dirs=bool(use_density_source_dirs),
    )
    fitness = eva.evaluate(code)
    if getattr(eva, "_last_error", None):
        return "FAILED\n" + str(eva._last_error) + "\n" + str(eva._last_traceback or "")
    return f"OK fitness={float(fitness):.6f}"

def add_new_seed(algorithm: str = "", code: str = "", candidate_code: str = "", seed_file: str = "seeds_insertships_go.json") -> str:
    if not code and candidate_code:
        code = candidate_code
    if not algorithm:
        return "Failed: must provide algorithm description."
    if not code:
        return "Failed: must provide code."
    
    seed_path = os.path.join(example_root, seed_file)
    seeds = []
    if os.path.exists(seed_path):
        with open(seed_path, "r", encoding="utf-8") as f:
            try:
                seeds = json.load(f)
            except Exception:
                seeds = []
    if not isinstance(seeds, list):
        seeds = []
    for s in seeds:
        if s.get("code", "") == code:
            return "Duplicate seed code."
    seeds.append({"algorithm": algorithm, "code": code})
    with open(seed_path, "w", encoding="utf-8") as f:
        json.dump(seeds, f, ensure_ascii=False, indent=2)
    return seed_path

def run_deep_analysis() -> str:
    stats = analyze_latest_results()
    best = stats.get("best_fitness", None)
    none_rate = stats.get("none_rate", None)
    last_error = stats.get("last_error", None)
    last_tb = stats.get("last_traceback", None)
    out = []
    out.append(f"best_fitness={best}")
    out.append(f"none_rate={none_rate}")
    if last_error:
        out.append(f"last_error={last_error}")
    if last_tb:
        out.append(f"last_traceback={last_tb[:1200]}")
    if none_rate is not None and float(none_rate) > 0:
        out.append("Diagnosis: Many candidates failed. Prefer compile-safe InsertShips and run run_code_review before add_new_seed.")
    if best is not None and float(best) >= 206.41536:
        out.append("Diagnosis: Stagnation at baseline. Consider refining InsertShips scoring or regret strategies.")
    return "\n".join(out)

def run_comprehensive_evaluation(
    sim_time_multi: int = 10,
    max_instances: int = 8,
    run_timeout_s: int = 120,
    objective_use_composite: bool = True,
    objective_res_weight: float = 0.2,
    dataset_density: str = "d25",
    sim_time_interval: int = 1,
    arrival_scale: float = 1.0,
    use_density_source_dirs: bool = False,
) -> str:
    stats = analyze_latest_results()
    best_code = stats.get("best_code", "")
    if not best_code:
        return "No best_code found. Run evolution first."

    os.environ["EOH_OBJECTIVE_USE_COMPOSITE"] = "1" if bool(objective_use_composite) else "0"
    os.environ["EOH_RES_WEIGHT"] = str(float(objective_res_weight))
    os.environ["EOH_RUN_TIMEOUT_S"] = str(int(run_timeout_s))
    eva = prob_insertships_go.Evaluation(
        sim_time_multi=int(sim_time_multi),
        max_instances=int(max_instances),
        run_timeout_s=int(run_timeout_s),
        dataset_density=dataset_density,
        sim_time_interval=int(sim_time_interval),
        arrival_scale=float(arrival_scale),
        use_density_source_dirs=bool(use_density_source_dirs),
    )
    avg = eva.evaluate(best_code)
    details = []
    try:
        details = json.loads(getattr(eva, "_last_traceback", "[]") or "[]")
    except Exception:
        details = []

    baseline = _parse_baseline(_baseline_path())

    report = "# InsertShips Comprehensive Evaluation\n\n"
    report += f"- Avg fitness: {avg:.6f}\n"
    report += f"- Baseline avg (final_result.txt): {float(np.mean(list(baseline.values()))):.6f}\n\n" if baseline else ""
    report += "| instance | cost | baseline | delta |\n|---|---:|---:|---:|\n"
    for d in details:
        name = d.get("instance", "")
        cost = d.get("cost", None)
        base = baseline.get(name, None)
        if cost is None:
            report += f"| {name} | N/A | {base if base is not None else 'N/A'} | N/A |\n"
        else:
            if base is None:
                report += f"| {name} | {float(cost):.6f} | N/A | N/A |\n"
            else:
                report += f"| {name} | {float(cost):.6f} | {float(base):.6f} | {float(cost-base):.6f} |\n"
    return report

def write_report(
    sim_time_multi: int = 10,
    max_instances: int = 8,
    run_timeout_s: int = 120,
    objective_use_composite: bool = True,
    objective_res_weight: float = 0.2,
    dataset_density: str = "d25",
    sim_time_interval: int = 1,
    arrival_scale: float = 1.0,
    use_density_source_dirs: bool = False,
) -> str:
    md = run_comprehensive_evaluation(
        sim_time_multi=int(sim_time_multi),
        max_instances=int(max_instances),
        run_timeout_s=int(run_timeout_s),
        objective_use_composite=bool(objective_use_composite),
        objective_res_weight=float(objective_res_weight),
        dataset_density=dataset_density,
        sim_time_interval=int(sim_time_interval),
        arrival_scale=float(arrival_scale),
        use_density_source_dirs=bool(use_density_source_dirs),
    )
    out_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"genroute_report_{time.strftime('%Y%m%d_%H%M%S')}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    return out_path

def generate_seeds_from_research(query: str, out_name: str = "seeds_insertships_go_research.json") -> str:
    summary = web_search(query)
    seed_src = os.path.abspath(os.path.join(example_root, "seeds_insertships_go.json"))
    if not os.path.exists(seed_src):
        return "Seed source not found: seeds_insertships_go.json"

    with open(seed_src, "r", encoding="utf-8") as f:
        seeds = json.load(f)
    if not isinstance(seeds, list) or not seeds:
        return "Seed source is empty or invalid JSON."

    notes_path = os.path.join(os.path.dirname(__file__), "research_notes.md")
    alg_note = f"Research query: {query}\nResearch summary: {summary}\nNotes file: {notes_path}"

    base = seeds[0]
    code = base.get("code", "")
    if not code:
        return "Base seed has no code."

    extra = [
        {
            "algorithm": "Research-guided seed (baseline code). " + alg_note,
            "code": code,
        },
        {
            "algorithm": "Research-guided seed (time-window aware regret). " + alg_note,
            "code": """func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch {
	var sm SortManager
	var inds []int
	var values []float64
	var flag bool = true

	for jj := range oris {
		inds = inds[:0]
		values = values[:0]
		for ii := 0; ii < dispatch.AssignsLen; ii++ {
			inds = append(inds, ii)
            // Enhanced scoring: Distance + Time urgency + Load penalty
            dist := cal_dis(dispatch.Assigns[ii].StationCurrent, oris[jj])
            time_urgency := float64(oris[jj].TimeEnd - dispatch.Assigns[ii].TimeCurrent)
            if time_urgency < 0 { time_urgency = 0 }
			values = append(values, dist + (1000.0 / (time_urgency + 1.0)) + float64(oris[jj].Load)*10.0)
		}
		sm.inds = inds
		sm.values = values
		sort.Sort(&sm)
		for ii := 0; ii < dispatch.AssignsLen; ii++ {
			flag = true
			ind := sm.inds[ii]
			if dispatch.AssignsLen < MAXASSIGNS && sm.values[ind] > cal_dis(dispatch.Assigns[MAXASSIGNS-1].StationCurrent, oris[jj]) {
				break
			}
			dispatch.Assigns[ind].AddShip(total_ship+jj, oris[jj], dess[jj])
			dispatch.Assigns[ind].GenRoute()
			if dispatch.Assigns[ind].Cost > 0 {
				flag = false
				break
			}
			dispatch.Assigns[ind].RemoveShip(total_ship + jj)
			dispatch.Assigns[ind].GenRoute()
		}
		if flag {
			dispatch.Assigns[dispatch.AssignsLen].AddShip(total_ship+jj, oris[jj], dess[jj])
			dispatch.Assigns[dispatch.AssignsLen].GenRoute()
			dispatch.AssignsLen += 1
		}
	}
	dispatch.RenewnTotalCost()
	return dispatch
}""",
        }
    ]

    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), out_name))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(seeds + extra, f, ensure_ascii=False, indent=2)
    return out_path


def finish() -> str:
    return "Task finished."
