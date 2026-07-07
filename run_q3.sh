#!/usr/bin/env bash
# Q3 BP 卡片消融一键运行脚本
# 用法: bash run_q3.sh [--dry-run]
# 自动从 ~/.config/auto-algo-opt/opencode.env 加载 API 密钥
set -euo pipefail
cd "$(dirname "$0")"

MANIFEST="eoh_rag_workspace/experiments/manifests/bp_ablation_cards_q3.json"
PYTHON3_10="/opt/homebrew/bin/python3.10"
DRY_RUN=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN="--dry-run" ;;
    *) echo "usage: $0 [--dry-run]"; exit 1 ;;
  esac
  shift
done

# 加载 API 密钥
export EOH_OFFICIAL_PYTHON="$PYTHON3_10"
export DEEPSEEK_API_KEY=$(grep '^DEEPSEEK_API_KEY=' ~/.config/auto-algo-opt/opencode.env | cut -d= -f2-)
export DEEPSEEK_API_ENDPOINT=$(grep '^DEEPSEEK_API_ENDPOINT=' ~/.config/auto-algo-opt/opencode.env | cut -d= -f2-)
export DEEPSEEK_MODEL=$(grep '^DEEPSEEK_MODEL=' ~/.config/auto-algo-opt/opencode.env | cut -d= -f2-)

if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  echo "ERROR: DEEPSEEK_API_KEY not set in ~/.config/auto-algo-opt/opencode.env"
  exit 1
fi

echo "API 已验证 | Python: $EOH_OFFICIAL_PYTHON | Model: $DEEPSEEK_MODEL"
echo "启动 Q3 消融(3臂×10 repeats,约 4.5h)"

python3 -m eoh_rag.experiments.batch_runner \
  --manifest "$MANIFEST" \
  --force $DRY_RUN \
  --shared-pool-dir eoh_rag_workspace/shared_pool_q3 \
  --output-dir eoh_rag_workspace/reports/bp_ablation_q3

echo "=== 运行完成,执行分析 ==="
python3 eoh_rag/experiments/reports/analyze_q3.py \
  --report-dir eoh_rag_workspace/reports/bp_ablation_q3
