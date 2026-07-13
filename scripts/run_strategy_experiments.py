"""Q3 与跨问题实验的统一 preflight/formal 入口。"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from eoh_rag.experiments.provider import get_provider_config
from eoh_rag.experiments.strategy_assets import load_and_validate_assets
from scripts.freeze_q3_mechanism_contexts import validate_frozen_contexts
from scripts.opencode_go_env import build_env, load_opencode_go_key

MANIFESTS={
    "proxy": ROOT/"eoh_rag_workspace/experiments/manifests/bp_ablation_cards_q3_proxy.json",
    "q3":ROOT/"eoh_rag_workspace/experiments/manifests/bp_ablation_cards_q3.json",
    "cross":ROOT/"eoh_rag_workspace/experiments/manifests/cross_problem_transfer_v1.json",
    "mechanism":ROOT/"eoh_rag_workspace/experiments/manifests/bp_q3_mechanism_discovery_v1.json",
    "mechanism_confirm":ROOT/"eoh_rag_workspace/experiments/manifests/bp_q3_fused_confirmation_v1.json",
    "m3_screen":ROOT/"eoh_rag_workspace/experiments/manifests/m3_operator_screen_v1.json",
    "m3_tsp_confirm":ROOT/"eoh_rag_workspace/experiments/manifests/m3_tsp_confirmation_v1.json",
    "inheritance_control":ROOT/"eoh_rag_workspace/experiments/manifests/inherited_pool_control_v1.json",
}
REPORT_ROOT = ROOT / "eoh_rag_workspace/reports/formal"

def _check_provider(name: str) -> tuple[bool,str]:
    config=get_provider_config(name); key=os.environ.get(config.api_key_env, "")
    if name == "opencode-go" and not key:
        key, _ = load_opencode_go_key()
    if not key: return False, f"missing {config.api_key_env}"
    # OpenCode Go 的边缘防护会拒绝 urllib 默认 User-Agent；与正式调用保持一致。
    request=urllib.request.Request(
        config.endpoint,
        data=json.dumps({"model":config.model,"messages":[{"role":"user","content":"Reply OK"}],"max_tokens":2}).encode(),
        headers={"Authorization":f"Bearer {key}","Content-Type":"application/json","Accept":"application/json","User-Agent":"eoh-experiment/1.0"},
    )
    try:
        with urllib.request.urlopen(request,timeout=30) as response: return 200 <= response.status < 300, f"HTTP {response.status}"
    except Exception as exc: return False, f"{type(exc).__name__}: {exc}"

def preflight(experiments: list[str], provider: str) -> int:
    checks=[]
    for name in experiments:
        manifest=MANIFESTS[name]
        proc=subprocess.run([sys.executable,"-m","eoh_rag.experiments.batch_runner","--manifest",str(manifest),"--no-run"],cwd=ROOT,text=True,capture_output=True)
        checks.append({"check":"manifest_dry_run","suite":name,"ok":proc.returncode==0,"detail":(proc.stdout+proc.stderr)[-500:]})
        manifest_payload=json.loads(manifest.read_text(encoding="utf-8"))
        if manifest_payload.get("context_lock"):
            try:
                lock_path=ROOT/manifest_payload["context_lock"]
                lock=validate_frozen_contexts(lock_path)
                checks.append({"check":"context_lock","suite":name,"ok":True,"detail":{"files":len(lock["files"]),"chars":lock["effective_context_chars"]}})
            except Exception as exc:
                checks.append({"check":"context_lock","suite":name,"ok":False,"detail":str(exc)})
    try:
        load_and_validate_assets(ROOT/"eoh_rag_workspace/experiments/strategies/abstract_strategies.json",ROOT/"eoh_rag_workspace/experiments/strategies/transfer_card_map.json")
        checks.append({"check":"strategy_assets","ok":True})
    except Exception as exc: checks.append({"check":"strategy_assets","ok":False,"detail":str(exc)})
    q3=json.loads(MANIFESTS["q3"].read_text(encoding="utf-8")); missing=[path for path in q3.get("held_out_set",[]) if not (ROOT/path).is_file()]
    registry=json.loads((ROOT/"eoh_rag_workspace/experiments/manifests/core_benchmark_registry.json").read_text(encoding="utf-8"))
    checks.append({"check":"held_out_readable","ok":not missing and len(registry.get("instances",[]))==22,"detail":{"missing":missing,"core_registry_count":len(registry.get("instances",[]))}})
    connected,detail=_check_provider(provider); checks.append({"check":"provider_connected","ok":connected,"detail":detail})
    result={"phase":"preflight","provider":provider,"checks":checks,"formal_allowed":all(check["ok"] for check in checks)}
    gate_path = REPORT_ROOT / "preflight_gate.json"
    gate_path.parent.mkdir(parents=True, exist_ok=True)
    gate_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result["formal_allowed"] else 2

def formal(experiments: list[str], provider: str, concurrency: int, resume: bool) -> int:
    failed=False
    child_env=os.environ.copy()
    if provider == "opencode-go":
        # 只在子进程内把 Go 凭证映射到既有 EoH 合约，认证路径与密钥均不落盘。
        child_env, _ = build_env("deepseek-v4-flash", "https://opencode.ai/zen/go/v1/chat/completions", preserve_existing=False)
    for name in experiments:
        command=[sys.executable,"-m","eoh_rag.experiments.batch_runner","--manifest",str(MANIFESTS[name]),"--output-dir",str(ROOT/"eoh_rag_workspace/reports/formal"),"--provider",provider,"--max-concurrent-runs",str(concurrency),"--force"]
        if resume: command.append("--resume")
        failed = subprocess.run(command,cwd=ROOT,env=child_env).returncode != 0 or failed
    return 1 if failed else 0

def proxy(provider: str, concurrency: int, resume: bool) -> int:
    preflight_gate = REPORT_ROOT / "preflight_gate.json"
    if not preflight_gate.is_file() or not json.loads(preflight_gate.read_text(encoding="utf-8")).get("formal_allowed"):
        print("ERROR: successful preflight_gate.json is required", file=sys.stderr)
        return 2
    exit_code = formal(["proxy"], provider, concurrency, resume)
    suite_dir = REPORT_ROOT / "bp_ablation_cards_q3_proxy"
    index_path = suite_dir / "run_index.json"
    rows = json.loads(index_path.read_text(encoding="utf-8")) if index_path.is_file() else []
    checks = {
        "provider_connected": True,
        "seed_recorded": len(rows) == 6 and all(isinstance(row.get("seed"), int) for row in rows),
        "held_out_readable": True,
        "summary_written": len(rows) == 6 and all((Path(row["output_dir"]) / "official_eoh_run_summary.json").is_file() for row in rows),
        "analysis_parseable": len(rows) == 6 and all(row.get("status") in {"ok", "skipped_complete"} for row in rows),
        "traceback_absent": len(rows) == 6 and all("traceback" not in str(row.get("detail", "")).lower() for row in rows),
    }
    result = {"phase": "proxy", "provider": provider, "run_count": len(rows), "checks": checks, "formal_allowed": exit_code == 0 and all(checks.values())}
    (REPORT_ROOT / "proxy_gate.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["formal_allowed"] else 3

def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--experiments",nargs="+",choices=["q3","cross","mechanism","mechanism_confirm","m3_screen","m3_tsp_confirm","inheritance_control"],required=True); parser.add_argument("--provider",choices=["opencode-go","deepseek"],default="opencode-go"); parser.add_argument("--phase",choices=["preflight","proxy","formal"],required=True); parser.add_argument("--max-concurrent-runs",type=int,default=1); parser.add_argument("--resume",action="store_true"); args=parser.parse_args()
    if args.phase == "preflight":
        raise SystemExit(preflight(args.experiments,args.provider))
    if args.phase == "proxy":
        raise SystemExit(proxy(args.provider,args.max_concurrent_runs,args.resume))
    proxy_gate = REPORT_ROOT / "proxy_gate.json"
    if not proxy_gate.is_file() or not json.loads(proxy_gate.read_text(encoding="utf-8")).get("formal_allowed"):
        print("ERROR: successful proxy_gate.json is required", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(formal(args.experiments,args.provider,args.max_concurrent_runs,args.resume))
if __name__=="__main__": main()
