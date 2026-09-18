# auto-algo-opt

让 Coding Agent 根据真实评测反馈，逐轮改进算法与光学设计。

你提供问题、模型配置和预算，Agent 负责提出思路、观察结果、调整下一轮方向。候选方案交给实际评测器验证，而不是由模型自己判断好坏。最终保留可复用的方案，以及每轮发生了什么、效果如何的记录。

## 能做什么

| 方向 | 当前支持 | 产出 |
|---|---|---|
| 组合优化 | 车辆路径（CVRP）、旅行商（TSP）、在线装箱（OBP） | 可执行的启发式算法代码 |
| 光学设计 | 单透镜（T1）、三片透镜（T3） | 可供光学评测器验证的处方 |

两条路线共用“规划 → 生成 → 评测 → 改进”的思路，但执行方式独立：

- **组合优化**：Coding Agent 指导搜索，官方 EoH 负责生成和演化算法。
- **光学设计**：直接生成、调整透镜处方，通过物理评测优化效果，不经过 EoH。

项目通过 Skill 为 Codex、Claude Code 等 Coding Agent 提供操作说明。可选 Memory 用于积累经验；每轮反馈和最终结果会汇总为进化过程表，便于观察改善、停滞和失败。

## 快速开始

先克隆仓库，在仓库根目录执行以下命令。两条路线使用不同的 Python 环境，按需安装即可。

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

### 光学设计

需要独立的 Python 3.12 环境，以及项目方提供的光学任务包：

```powershell
py -3.12 -m venv .venv-optics
& .venv-optics/Scripts/python.exe -m pip install ./extensions/optics
& .venv-optics/Scripts/python.exe -m artifact_session --help
```

随后按 [光学使用指南](extensions/optics/README.md) 导入任务，并加载 [optical-design Skill](extensions/optics/skills/optical-design/SKILL.md) 开始优化。任务原始数据不包含在仓库中。

两条路线的 API 密钥均通过环境变量提供，请勿写入代码或提交到仓库。

## 当前进展

**组合优化**已接入官方 EoH，支持跨轮搜索、候选保存和重载评测。在线装箱提供小规模 benchmark，用于校准与流程验证；目前不宣称完整复现 EoH-S。数据范围见 [OBP 说明](docs/obp_evolution_mini.md)，实验结果见 [报告索引](reports/README.md)。

**光学设计**已完成一次真实 T1 优化：由 Luna 规划、DeepSeek 生成，经过 9 轮、170 个候选，最佳可行处方的在线评分 Q 为 **0.5552**。实际使用 195 / 500 的物理评测额度后主动结束，通过了后续审计与独立验证器检查。

这仍是单次实验，不代表全局最优，也不构成独立波前认证。当前光学验证环境为 Windows，Linux 尚未验收，T3 仅完成离线验证。完整结果与限制见 [T1 实验摘要](reports/optics_t1_luna_20260917.md)。

## 进一步了解

- [文档导航](docs/README.md)：架构、配置和详细操作
- [实验与验收报告](reports/README.md)：结果、证据与已知限制
- [离线知识库](docs/knowledge_base.md)：文献与历史经验整理
- [历史归档](reports/archive/README.md)：早期方案与研究记录
