"""从已审计卡片冻结去问题化中文策略与跨问题映射。"""
from __future__ import annotations
import hashlib, json
from pathlib import Path

DESCRIPTIONS = {
"obp_first_fit":"优先采用当前最早满足约束的可行方案，减少额外结构的开启。",
"obp_best_fit":"优先采用执行后剩余空间最少但仍可行的方案，提高已有空间利用率。",
"obp_harmonic":"按规模区间分层处理候选项，让相近尺度遵循一致的选择规则。",
"obp_funsearch_residual_poly":"综合剩余空间与非线性惩罚排序，在紧凑利用和后续可调空间之间平衡。",
"tsp_regret_insertion":"优先处理替代选择会迅速变差的候选，同时控制当前增加的代价。",
"tsp_farthest_insertion":"先吸收离当前结构较远的候选，避免它们在后期形成昂贵补接。",
"tsp_nearest_insertion":"优先扩展当前增量代价较小的候选，逐步构造稳定结构。",
"tsp_two_opt_awareness":"选择时兼顾潜在交叉与局部重排空间，减少后续修复成本。",
"cvrp_regret_insertion":"优先处理替代位置会造成明显额外代价的候选，并把容量仅作为可行性约束。",
"cvrp_far_first":"先处理远离公共起点的候选，降低后期单独访问造成的高代价。",
"cvrp_savings":"优先合并能相对独立执行显著节约总代价的候选组合。",
"cvrp_sweep":"按空间方位形成连续处理顺序，再在每个局部范围内满足资源约束。"}
PROBLEM = {key:("bp_online" if key.startswith("obp_") else "tsp_construct" if key.startswith("tsp_") else "cvrp_construct") for key in DESCRIPTIONS}
TARGETS={"bp_online":["tsp_construct","cvrp_construct"],"tsp_construct":["bp_online","cvrp_construct"],"cvrp_construct":["bp_online","tsp_construct"]}

def main() -> None:
    corpus_path=Path("eoh_rag_workspace/rag/corpus/algorithm_cards.jsonl")
    cards={row["id"]:row for row in (json.loads(line) for line in corpus_path.read_text(encoding="utf-8").splitlines() if line.strip())}
    records=[]
    for card_id, description in DESCRIPTIONS.items():
        source=json.dumps(cards[card_id],ensure_ascii=False,sort_keys=True,separators=(",",":"))
        records.append({"schema_version":"abstract-strategy/v1","abstract_strategy_id":f"as_{PROBLEM[card_id]}_{card_id}","source_problem":PROBLEM[card_id],"source_card_id":card_id,"abstract_description":description,"target_problem_compatibility":TARGETS[PROBLEM[card_id]],"source_content_sha256":hashlib.sha256(source.encode("utf-8")).hexdigest()})
    out=Path("eoh_rag_workspace/experiments/strategies"); out.mkdir(parents=True,exist_ok=True)
    (out/"abstract_strategies.json").write_text(json.dumps({"schema_version":"abstract-strategy-set/v1","strategies":records},ensure_ascii=False,indent=2),encoding="utf-8")
    mapping={
      "bp_online":{"core_local":["obp_first_fit","obp_best_fit"],"extra_local":["obp_harmonic","obp_funsearch_residual_poly"],"external_abstract":["as_tsp_construct_tsp_regret_insertion","as_cvrp_construct_cvrp_savings"]},
      "tsp_construct":{"core_local":["tsp_regret_insertion","tsp_nearest_insertion"],"extra_local":["tsp_farthest_insertion","tsp_two_opt_awareness"],"external_abstract":["as_bp_online_obp_best_fit","as_cvrp_construct_cvrp_far_first"]},
      "cvrp_construct":{"core_local":["cvrp_regret_insertion","cvrp_savings"],"extra_local":["cvrp_far_first","cvrp_sweep"],"external_abstract":["as_bp_online_obp_harmonic","as_tsp_construct_tsp_two_opt_awareness"]}}
    (out/"transfer_card_map.json").write_text(json.dumps({"schema_version":"transfer-card-map/v1","max_chars":2500,"problems":mapping},ensure_ascii=False,indent=2),encoding="utf-8")
    strategy_by_id = {row["abstract_strategy_id"]: row for row in records}
    context_dir = out / "contexts"
    context_dir.mkdir(parents=True, exist_ok=True)
    for problem, config in mapping.items():
        local_sections = [cards[card_id]["content"].strip() for card_id in config["core_local"] + config["extra_local"]]
        mixed_sections = [cards[card_id]["content"].strip() for card_id in config["core_local"]]
        mixed_sections.extend(strategy_by_id[strategy_id]["abstract_description"] for strategy_id in config["external_abstract"])
        for arm, sections in (("local_only", local_sections), ("mixed_abstract", mixed_sections)):
            context = "\n\n---\n\n".join(sections)
            if len(context) > 2500:
                raise ValueError(f"context exceeds max_chars: {problem}/{arm} ({len(context)})")
            (context_dir / f"{problem}_{arm}.txt").write_text(context + "\n", encoding="utf-8")

if __name__=="__main__": main()
