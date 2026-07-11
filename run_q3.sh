#!/usr/bin/env bash
# Q3 BP 卡片消融一键入口；默认顺序执行三臂，避免跨臂共享种群污染比较。
# 用法：bash run_q3.sh [--dry-run]
set -euo pipefail

REPOSITORY_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPOSITORY_ROOT"

MANIFEST_PATH="eoh_rag_workspace/experiments/manifests/bp_ablation_cards_q3.json"
HELD_OUT_DIRECTORY="eoh_rag_workspace/problems/bp_online/held_out"
OUTPUT_DIRECTORY="eoh_rag_workspace/reports/bp_ablation_q3"
SUITE_NAME="bp_ablation_cards_q3"
DRY_RUN=false

usage() {
  echo "usage: $0 [--dry-run]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
  shift
done

# Windows Git Bash 常见命令是 python，Linux/macOS 通常是 python3；用户可显式覆盖。
if [[ -z "${PYTHON_BIN:-}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "ERROR: Python not found. Set PYTHON_BIN to a Python 3.10+ executable." >&2
    exit 1
  fi
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1 && [[ ! -x "$PYTHON_BIN" ]]; then
  echo "ERROR: PYTHON_BIN is not executable: $PYTHON_BIN" >&2
  exit 1
fi

export PYTHON_BIN
export EOH_OFFICIAL_PYTHON="${EOH_OFFICIAL_PYTHON:-$PYTHON_BIN}"
AUTO_ALGO_OPT_ENV_FILE="${AUTO_ALGO_OPT_ENV_FILE:-${XDG_CONFIG_HOME:-${HOME:-}/.config}/auto-algo-opt/opencode.env}"
export AUTO_ALGO_OPT_ENV_FILE

if [[ ! -f "$MANIFEST_PATH" ]]; then
  echo "ERROR: Q3 manifest is missing: $MANIFEST_PATH" >&2
  echo "Restore the tracked manifest before running Q3." >&2
  exit 1
fi

missing_datasets=()
for dataset_name in hifo_1k_C100.pkl hifo_5k_C100.pkl hifo_10k_C100.pkl; do
  if [[ ! -f "$HELD_OUT_DIRECTORY/$dataset_name" ]]; then
    missing_datasets+=("$dataset_name")
  fi
done

if [[ ${#missing_datasets[@]} -gt 0 ]]; then
  echo "ERROR: Q3 held-out datasets are missing: ${missing_datasets[*]}" >&2
  echo "Prepare and verify them with:" >&2
  echo "  \"$PYTHON_BIN\" scripts/prepare_hifo_bp_data.py" >&2
  echo "Or import an existing HiFo checkout with:" >&2
  echo "  \"$PYTHON_BIN\" scripts/prepare_hifo_bp_data.py --source-dir <HiFo-Prompt>" >&2
  exit 1
fi

load_api_environment() {
  # 只读取允许的三个键，绝不 source 配置文件，避免配置内容被当成 shell 执行。
  local existing_api_key="${DEEPSEEK_API_KEY:-}"
  local existing_api_endpoint="${DEEPSEEK_API_ENDPOINT:-}"
  local existing_model="${DEEPSEEK_MODEL:-}"
  local line
  local key
  local value

  if [[ -f "$AUTO_ALGO_OPT_ENV_FILE" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
      line="${line%$'\r'}"
      [[ "$line" =~ ^[[:space:]]*$ ]] && continue
      [[ "$line" =~ ^[[:space:]]*# ]] && continue
      [[ "$line" != *=* ]] && continue

      key="${line%%=*}"
      value="${line#*=}"
      key="${key#"${key%%[![:space:]]*}"}"
      key="${key%"${key##*[![:space:]]}"}"
      value="${value#"${value%%[![:space:]]*}"}"
      value="${value%"${value##*[![:space:]]}"}"

      # 仅去除成对的外围引号，不解释命令替换、变量或反斜杠转义。
      if [[ ${#value} -ge 2 ]]; then
        if [[ "${value:0:1}" == '"' && "${value: -1}" == '"' ]] || \
           [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
          value="${value:1:${#value}-2}"
        fi
      fi

      case "$key" in
        DEEPSEEK_API_KEY)
          if [[ -z "$existing_api_key" ]]; then
            export DEEPSEEK_API_KEY="$value"
            existing_api_key="$value"
          fi
          ;;
        DEEPSEEK_API_ENDPOINT)
          if [[ -z "$existing_api_endpoint" ]]; then
            export DEEPSEEK_API_ENDPOINT="$value"
            existing_api_endpoint="$value"
          fi
          ;;
        DEEPSEEK_MODEL)
          if [[ -z "$existing_model" ]]; then
            export DEEPSEEK_MODEL="$value"
            existing_model="$value"
          fi
          ;;
      esac
    done < "$AUTO_ALGO_OPT_ENV_FILE"
  fi
}

runner_arguments=(
  -m eoh_rag.experiments.batch_runner
  --manifest "$MANIFEST_PATH"
  --output-dir "$OUTPUT_DIRECTORY"
)

if [[ "$DRY_RUN" == true ]]; then
  # 预演只验证路径和展开命令，不读取密钥文件，也不要求 API 密钥。
  runner_arguments+=(--dry-run)
  echo "Q3 dry-run | Python: $PYTHON_BIN | Official Python: $EOH_OFFICIAL_PYTHON"
else
  load_api_environment
  if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
    echo "ERROR: DEEPSEEK_API_KEY is not set." >&2
    echo "Export it directly or set AUTO_ALGO_OPT_ENV_FILE to a readable env file." >&2
    exit 1
  fi
  runner_arguments+=(--force)
  echo "Starting Q3 ablation (3 arms x 10 paired repeats)."
fi

"$PYTHON_BIN" "${runner_arguments[@]}"

if [[ "$DRY_RUN" == true ]]; then
  echo "Q3 dry-run completed; no API key was required."
  exit 0
fi

report_directory="$OUTPUT_DIRECTORY/$SUITE_NAME"
echo "=== Q3 runs completed; analyzing held-out results ==="
"$PYTHON_BIN" eoh_rag/experiments/reports/analyze_q3.py \
  --report-dir "$report_directory"
