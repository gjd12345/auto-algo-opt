# 复现指南

本仓库自包含:主线评测引擎 `official_eoh/` 已内置于仓内,复现基线与实验**无需克隆任何外部仓库**。

## 前置条件

- Python >= 3.10(内置评测引擎的类型注解要求 3.10+)
- 一个 OpenAI 兼容的大模型 API(DeepSeek / JoyAI 等)—— 仅**真实进化实验**需要
- Go >= 1.20 —— 可选,仅 InsertShips 系列的 Go 评测轨道需要;缺失时相关测试自动跳过

## 快速开始(只跑单元测试)

```bash
pip install -e ".[dev]"    # 安装本包 + pytest
pytest tests/ -v
```

单元测试使用 mock,不需要任何大模型 API 密钥。本地有 Go 工具链时约 `347 passed, 1 skipped`;
无 Go 时依赖 Go 的测试自动跳过。

## 环境变量

| 变量 | 何时需要 | 说明 |
|------|----------|------|
| `DEEPSEEK_API_KEY` | 真实进化实验 | 大模型 API 密钥 |
| `DEEPSEEK_API_ENDPOINT` | 真实进化实验 | 例如 `api.deepseek.com` |
| `DEEPSEEK_MODEL` | 真实进化实验 | 例如 `deepseek-v4-pro` |
| `EOH_OFFICIAL_ROOT` | 可选 | 主线评测引擎路径;默认指向内置的 `official_eoh/`,一般无需设置 |
| `EOH_OFFICIAL_PYTHON` | 可选 | 运行评测子进程的 Python;默认使用当前解释器 |

大模型访问配置写进 `~/.config/auto-algo-opt/opencode.env`(键值对形式),运行脚本会 `export` 后再启动:

```bash
# ~/.config/auto-algo-opt/opencode.env 示例
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_API_ENDPOINT=api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
```

## 跑真实进化实验

内置评测引擎位于 `official_eoh/`,运行器默认 `official_root` 就指向它,无需外部安装。
只需在 Python 3.10+ 环境补装真实实验用到的依赖:

```bash
pip install -e ".[official-eoh]"   # requests / torch / numba / python-docx
```

跑一次最小实验:

```bash
export $(grep -v '^#' ~/.config/auto-algo-opt/opencode.env | xargs)
python -m eoh_rag.experiments.batch_runner \
  --manifest eoh_rag_workspace/experiments/manifests/high_gen_bp_online.json \
  --force --shared-pool-dir eoh_rag_workspace/shared_pool \
  --output-dir eoh_rag_workspace/reports/run1
```

多进程 Island Model 一键并行:`bash scripts/launch_island.sh`。

## 精确复现基线(离线,不调用大模型)

主线三题的最优代码可用内置引擎直接复算,不涉及任何 API 调用。
需在 **Python 3.10+** 环境安装 `.[official-eoh]`(离线复算会经由 `prob` 导入内置 LLM 接口,
因此需要 `numpy` / `joblib` / `requests` 到位,由该 extra 与基础依赖一并提供):

```bash
python3 -c "
import sys; sys.path.insert(0, 'official_eoh/examples/bp_online')
from prob import BPONLINE
import numpy as np

def score(item, bins):
    residual = bins - item
    utilization = np.exp(item / (residual + item + 1e-9))
    penalty = np.where((residual > 0) & (residual < 2*item), (residual - item)**2 / (item + 1e-9), 0)
    return utilization - penalty

print(BPONLINE(capacity=100).evaluate_program('', score))
# 期望输出:0.006741...
"
```

TSP / CVRP 用 `evidence/final_batch_20260630/best_codes/{tsp_construct,cvrp_construct}_best.py`
里的 `select_next_node`,分别得到 6.00393 / 12.35639。
更多复现步骤见 `evidence/final_batch_20260630/REPRODUCE.md`。

## 只跑单元测试时不需要的东西

以下仅在跑真实进化实验(或离线复算基线)时才需要:

- `.[official-eoh]` extra 依赖(`requests` / `torch` / `numba` / `python-docx`)
- 大模型 API 访问与 `~/.config/auto-algo-opt/opencode.env`
