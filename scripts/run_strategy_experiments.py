"""Q3 与跨问题实验的统一 preflight/formal 入口。"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from eoh_rag.experiments.provider import get_provider_config
from eoh_rag.experiments.strategy_assets import load_and_validate_assets
from scripts.opencode_go_env import load_opencode_go_key

MANIFESTS={"q3":ROOT/"eoh_rag_workspace/experiments/manifests/bp_ablation_cards_q3.json","cross":ROOT/"eoh_rag_workspace/experiments/manifests/cross_problem_transfer_v1.json"}

def _check_provider(name: str) -> tuple[bool,str]:
    config=get_provider_config(name); key=os.environ.get(config.api_key_env, "")
    if name == "opencode-go" and not key:
        key, _ = load_opencode_go_key()
    if not key: return False, f"missing {config.api_key_env}"
    request=urllib.request.Request(config.endpoint,data=json.dumps({"model":config.model,"messages":[{"role":"user","content":"Reply OK"}],"max_tokens":2}).encode(),headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(request,timeout=30) as response: return 200 <= response.status < 300, f"HTTP {response.status}"
    except Exception as exc: return False, f"{type(exc).__name__}: {exc}"

def preflight(experiments: list[str], provider: str) -> int:
    checks=[]
    for name in experiments:
        manifest=MANIFESTS[name]
        proc=subprocess.run([sys.executable,"-m","eoh_rag.experiments.batch_runner","--manifest",str(manifest),"--no-run"],cwd=ROOT,text=True,capture_output=True)
        checks.append({"check":"manifest_dry_run","suite":name,"ok":proc.returncode==0,"detail":(proc.stdout+proc.stderr)[-500:]})
    try:
        load_and_validate_assets(ROOT/"eoh_rag_workspace/experiments/strategies/abstract_strategies.json",ROOT/"eoh_rag_workspace/experiments/strategies/transfer_card_map.json")
        checks.append({"check":"strategy_assets","ok":True})
    except Exception as exc: checks.append({"check":"strategy_assets","ok":False,"detail":str(exc)})
    q3=json.loads(MANIFESTS["q3"].read_text(encoding="utf-8")); missing=[path for path in q3.get("held_out_set",[]) if not (ROOT/path).is_file()]
    registry=json.loads((ROOT/"eoh_rag_workspace/experiments/manifests/core_benchmark_registry.json").read_text(encoding="utf-8"))
    checks.append({"check":"held_out_readable","ok":not missing and len(registry.get("instances",[]))==22,"detail":{"missing":missing,"core_registry_count":len(registry.get("instances",[]))}})
    connected,detail=_check_provider(provider); checks.append({"check":"provider_connected","ok":connected,"detail":detail})
    result={"phase":"preflight","provider":provider,"checks":checks,"formal_allowed":all(check["ok"] for check in checks)}
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result["formal_allowed"] else 2

def formal(experiments: list[str], provider: str, concurrency: int, resume: bool) -> int:
    failed=False
    for name in experiments:
        command=[sys.executable,"-m","eoh_rag.experiments.batch_runner","--manifest",str(MANIFESTS[name]),"--output-dir",str(ROOT/"eoh_rag_workspace/reports/formal"),"--provider",provider,"--max-concurrent-runs",str(concurrency),"--force"]
        if resume: command.append("--resume")
        failed = subprocess.run(command,cwd=ROOT).returncode != 0 or failed
    return 1 if failed else 0

def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--experiments",nargs="+",choices=["q3","cross"],required=True); parser.add_argument("--provider",choices=["opencode-go","deepseek"],default="opencode-go"); parser.add_argument("--phase",choices=["preflight","formal"],required=True); parser.add_argument("--max-concurrent-runs",type=int,default=1); parser.add_argument("--resume",action="store_true"); args=parser.parse_args()
    raise SystemExit(preflight(args.experiments,args.provider) if args.phase=="preflight" else formal(args.experiments,args.provider,args.max_concurrent_runs,args.resume))
if __name__=="__main__": main()
