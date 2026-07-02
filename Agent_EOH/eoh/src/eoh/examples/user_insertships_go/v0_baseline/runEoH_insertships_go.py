import argparse
import importlib
import json
import os
import sys


def _load_config(config_path: str) -> dict:
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
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

def _get_key(env_name: str, config: dict, config_key: str) -> str:
    return os.environ.get(env_name) or config.get(config_key, "") or ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--loops", type=int, default=1)
    parser.add_argument("--gens", type=int, default=1)
    parser.add_argument("--seed-path", type=str, default="")
    parser.add_argument("--sim-time-multi", type=int, default=1000000)
    parser.add_argument("--max-instances", type=int, default=1)
    args = parser.parse_args()

    src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    example_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    if example_root not in sys.path:
        sys.path.insert(0, example_root)

    from eoh import EVOL
    from eoh.utils.getParas import Paras
    import prob_insertships_go

    config_path = os.path.join(example_root, "v2_agent", "config.json")
    config = _load_config(config_path)
    if not config:
        alt = _find_user_cvrp_config(os.path.dirname(example_root))
        if alt:
            config = _load_config(alt)
    deepseek_api_key = _get_key("DEEPSEEK_API_KEY", config, "deepseek_api_key")

    seed_default = os.path.join(example_root, "seeds_insertships_go.json")
    seed_path = os.path.abspath(args.seed_path) if args.seed_path else seed_default

    for _ in range(int(args.loops)):
        importlib.reload(prob_insertships_go)
        problem_instance = prob_insertships_go.Evaluation(
            sim_time_multi=int(args.sim_time_multi),
            max_instances=int(args.max_instances),
        )

        paras = Paras()
        paras.exp_output_path = os.path.join(example_root, "results_insertships_v0")
        paras.set_paras(
            method="eoh",
            problem=problem_instance,
            llm_api_endpoint="api.deepseek.com",
            llm_api_key=deepseek_api_key,
            llm_model="deepseek-chat",
            ec_pop_size=4,
            ec_n_pop=int(args.gens),
            ec_operators=["m1","m2"],
            exp_n_proc=4,
            exp_use_seed=True,
            exp_seed_path=seed_path,
            eva_timeout=120,
            eva_numba_decorator=False,
        )

        evolution = EVOL(paras)
        evolution.run()


if __name__ == "__main__":
    main()
