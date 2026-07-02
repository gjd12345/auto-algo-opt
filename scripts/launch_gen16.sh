#!/bin/bash
# Gen=16 exploration — seeded from gen=8 best results
set -e
export $(grep -v '^#' ~/.config/auto-algo-opt/opencode.env | xargs)
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

POOL="eoh_rag_workspace/shared_pool"

# Best run dirs from gen=8 island model
BP_BEST="eoh_rag_workspace/reports/auto_experiment_reports/island_1/high_gen_bp_online/run_bp_online_E2_highgen_g8_r5"
CVRP_BEST="eoh_rag_workspace/reports/auto_experiment_reports/island_5/high_gen_cvrp_construct/run_cvrp_construct_E2_highgen_g8_r10"
TSP_BEST="eoh_rag_workspace/reports/auto_experiment_reports/island_5/high_gen_tsp_construct/run_tsp_construct_E2_highgen_g8_r17"

# TSP gen=16 × 3 parallel
for i in 1 2 3; do
  python3 -m eoh_rag.experiments.eoh_single_runner \
    --problem tsp_construct --arm literature_rag \
    --pop-size 6 --generations 16 --operators e1,e2,m1,m2 \
    --n-processes 1 --eval-timeout-s 40 --llm-timeout-s 180 --run-timeout-s 7200 \
    --output-dir "eoh_rag_workspace/reports/auto_experiment_reports/gen16_tsp_${i}" \
    --official-root /private/tmp/EoH-main --python /private/tmp/eoh_official_venv/bin/python \
    --rag-top-k 2 --rag-max-chars 2500 \
    --rag-query "tsp construct select next node distance nearest insertion regret farthest" \
    --selected-card-ids "tsp_regret_insertion,tsp_nearest_neighbor,tsp_farthest_insertion,tsp_nearest_insertion,tsp_two_opt_awareness" \
    --candidate-card-source candidate_card_ids \
    --rag-rerank llm \
    --outcome-file eoh_rag_workspace/rag/corpus/card_outcomes.jsonl \
    --prev-run-dir "$TSP_BEST" \
    > "/tmp/gen16_tsp_${i}.log" 2>&1 &
done

# CVRP gen=16 × 3 parallel
for i in 1 2 3; do
  python3 -m eoh_rag.experiments.eoh_single_runner \
    --problem cvrp_construct --arm literature_rag \
    --pop-size 6 --generations 16 --operators e1,e2,m1,m2 \
    --n-processes 1 --eval-timeout-s 40 --llm-timeout-s 180 --run-timeout-s 7200 \
    --output-dir "eoh_rag_workspace/reports/auto_experiment_reports/gen16_cvrp_${i}" \
    --official-root /private/tmp/EoH-main --python /private/tmp/eoh_official_venv/bin/python \
    --rag-top-k 2 --rag-max-chars 2500 \
    --rag-query "cvrp construct select next node distance farthest cluster regret depot capacity" \
    --selected-card-ids "cvrp_regret_insertion,cvrp_far_first,cvrp_savings,cvrp_nearest_capacity,cvrp_sweep" \
    --candidate-card-source candidate_card_ids \
    --rag-rerank llm \
    --outcome-file eoh_rag_workspace/rag/corpus/card_outcomes.jsonl \
    --prev-run-dir "$CVRP_BEST" \
    > "/tmp/gen16_cvrp_${i}.log" 2>&1 &
done

# BP gen=16 × 3 parallel
for i in 1 2 3; do
  python3 -m eoh_rag.experiments.eoh_single_runner \
    --problem bp_online --arm literature_rag \
    --pop-size 6 --generations 16 --operators e1,e2,m1,m2 \
    --n-processes 1 --eval-timeout-s 40 --llm-timeout-s 180 --run-timeout-s 7200 \
    --output-dir "eoh_rag_workspace/reports/auto_experiment_reports/gen16_bp_${i}" \
    --official-root /private/tmp/EoH-main --python /private/tmp/eoh_official_venv/bin/python \
    --rag-top-k 2 --rag-max-chars 2500 \
    --rag-query "online bin packing item size fit residual capacity utilization heuristic adaptive" \
    --selected-card-ids "obp_first_fit,obp_best_fit,obp_worst_fit,obp_harmonic,obp_funsearch_residual_poly,obp_eoh_util_sqrt_exp" \
    --candidate-card-source candidate_card_ids \
    --rag-rerank llm \
    --outcome-file eoh_rag_workspace/rag/corpus/card_outcomes.jsonl \
    --prev-run-dir "$BP_BEST" \
    > "/tmp/gen16_bp_${i}.log" 2>&1 &
done

echo "Launched $(jobs -p | wc -l) gen=16 processes"
