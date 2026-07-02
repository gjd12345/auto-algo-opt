#!/bin/bash
# Island Model Launcher — 15 parallel processes with shared pool
set -e
export $(grep -v '^#' ~/.config/auto-algo-opt/opencode.env | xargs)
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

POOL="eoh_rag_workspace/shared_pool"
rm -rf eoh_rag_workspace/reports/auto_experiment_reports/island_*

for prob in tsp_construct cvrp_construct bp_online; do
  for i in 1 2 3 4 5; do
    python3 -m eoh_rag.experiments.batch_runner \
      --manifest "eoh_rag_workspace/experiments/manifests/high_gen_${prob}.json" \
      --force --shared-pool-dir "$POOL" \
      --output-dir "eoh_rag_workspace/reports/auto_experiment_reports/island_${i}" \
      > "/tmp/island_${prob}_${i}.log" 2>&1 &
  done
done

echo "Launched $(jobs -p | wc -l) processes"
wait
echo "All done"
