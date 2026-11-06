# auto-algo-opt

让 Coding Agent 根据真实评测反馈，逐轮改进启发式算法。

你提供问题、模型配置和预算，Agent 负责提出思路、观察结果、调整下一轮方向。候选方案交给实际评测器验证，而不是由模型自己判断好坏。最终保留可复用的方案，以及每轮发生了什么、效果如何的记录。

## 能做什么

| 方向 | 当前支持 | 产出 |
|---|---|---|
| 组合优化 | 车辆路径（CVRP）、旅行商（TSP）、在线装箱（OBP） | 可执行的启发式算法代码 |

研究路线：Coding Agent 指导搜索并做出轮间决策，官方 EoH 负责轮内生成与演化，确定性评测器负责结果裁决，三者权限分离。

项目通过 Skill 为 Codex、Claude Code 等 Coding Agent 提供操作说明。可选 Memory 用于积累经验；每轮反馈和最终结果会汇总为进化过程表，便于观察改善、停滞和失败。

## 快速开始

先克隆仓库，在仓库根目录执行以下命令。

### 组合优化

需要 Python 3.11。以下是 Windows PowerShell 示例：

```powershell
py -3.11 -m venv .venv-co
& .venv-co/Scripts/python.exe -m pip install -e ".[dev,eoh]"
& .venv-co/Scripts/python.exe -m agent_skill_loop smoke --problem cvrp_construct --output outputs/offline_smoke
```

这会运行一次离线流程检查，**不调用付费模型**。重复运行时请换一个新的输出目录。

Linux / WSL 使用 `python3.11` 创建环境，并将解释器路径换为 `.venv-co/bin/python`。

开始真实优化时，需配置模型 API、设置预算，并让 Coding Agent 加载 [algorithm-optimization Skill](skills/algorithm-optimization/SKILL.md)。完整操作见 [两轮运行示例](skills/algorithm-optimization/references/examples/two-round-run.md)。

模型 API 密钥通过环境变量提供，请勿写入代码或提交到仓库。

## 当前进展

**组合优化**已接入官方 EoH，支持跨轮搜索、候选保存和重载评测。在线装箱提供小规模 benchmark，用于校准与流程验证；目前不宣称完整复现 EoH-S。数据范围见 [OBP 说明](docs/obp_evolution_mini.md)，实验结果见 [报告索引](reports/README.md)。

**研究闭环**是当前主线：在固定预算下，Agent 如何利用真实执行证据、显式反思与历史经验改进搜索。相关合同见 [Research Loop v2](docs/research-loop-v2.md)，机制设计与已知限制见 [证据说明](reports/README.md)。

> 已归档：早期 EOH-RAG / FME 研究、光学处方优化与 Six Mirror、Go 求解器。它们保留在 `archive/` 与 Git tag 中，不参与当前运行时，也不在 CI 中收集。

## 进一步了解

- [文档导航](docs/README.md)：架构、配置和详细操作
- [实验与验收报告](reports/README.md)：结果、证据与已知限制
- [离线知识库](docs/knowledge_base.md)：文献与历史经验整理
- [历史归档](reports/archive/README.md)：早期方案与研究记录
