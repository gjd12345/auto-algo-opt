#!/usr/bin/env bash
# Q3 BP 卡片消融一键运行脚本
# 用法: bash run_q3.sh [--parallel] [--dry-run]
# 先确保 ~/.config/auto-algo-opt/opencode.env 已填好真实密钥
set -euo pipefail
cd "$(dirname "$0")"

MANIFEST="eoh_rag_workspace/experiments/manifests/bp_ablation_cards_q3.json"
DRY_RUN=""
ARM_FILTER=""
PARALLEL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN="--dry-run" ;;
    --parallel) PARALLEL="yes" ;;
    --arm) shift; ARM_FILTER="$1" ;;
    *) echo "usage: $0 [--parallel] [--dry-run] [--arm pure|generic|answer]"; exit 1 ;;
  esac
  shift
done

# 验证 API 配置
if [ -f ~/.config/auto-algo-opt/opencode.env ]; then
  source ~/.config/auto-algo-opt/opencode.env
fi
if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  echo "ERROR: DEEPSEEK_API_KEY not set. Fill ~/.config/auto-algo-opt/opencode.env"
  exit 1
fi

if [ "$PARALLEL" = "yes" ] && [ -z "$ARM_FILTER" ]; then
  # 三臂并行（需各自独立 shared_pool + output_dir）
  for arm in pure generic answer; do
    (python3 -m eoh_rag.experiments.batch_runner \
      --manifest "$MANIFEST" \
      --arm-filter "$arm" \
      --force $DRY_RUN \
      --shared-pool-dir "eoh_rag_workspace/shared_pool_q3_${arm}" \
      --output-dir "eoh_rag_workspace/reports/bp_ablation_q3/${arm}" \
      > "q3_${arm}.log" 2>&1
    echo "[DONE] arm=$arm exit=$?") &
  done
  wait
  echo "All 3 arms done. See q3_{pure,generic,answer}.log"
elif [ -n "$ARM_FILTER" ]; then
  # 单臂运行（用于 preflight 或单独臂）
  python3 -m eoh_rag.experiments.batch_runner \
    --manifest "$MANIFEST" \
    --arm-filter "$ARM_FILTER" \
    --force $DRY_RUN \
    --shared-pool-dir "eoh_rag_workspace/shared_pool_q3_${ARM_FILTER}" \
    --output-dir "eoh_rag_workspace/reports/bp_ablation_q3/${ARM_FILTER}"
else
  # 顺序三臂（默认）
  python3 -m eoh_rag.experiments.batch_runner \
    --manifest "$MANIFEST" \
    --force $DRY_RUN \
    --shared-pool-dir eoh_rag_workspace/shared_pool_q3 \
    --output-dir eoh_rag_workspace/reports/bp_ablation_q3
fi
