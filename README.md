# auto-algo-opt

面向**组合优化自动启发式算法设计**的自主研究代理与闭环演化框架。项目将分层接口设计、冻结官方 EoH 演化内核、进化轨迹自适应控制与四层可审计记忆闭环整合为统一底座，支持 **CVRP、TSP、Online OBP、Offline BPP**。

---

## 核心功能（Core Features）

```mermaid
flowchart LR
    B["标准基准与盲测隔离\ndev · select · 仓外 blind"] --> RA["自主研究代理与分层接口\nresearch_agent/ + L1–L3"]
    RA --> EOH["冻结 EoH 演化内核\neoh_frozen/ + 共享硬预算"]
    EOH --> CTRL["轨迹控制与五关校验\n防膨胀筛查 · 查重 · 早停"]
    CTRL <--> MEM["四层记忆与闭环评估\nAuto-Dream + 配对检验"]
```

- **分层接口与诊断驱动研究代理（`research_agent/` + `agent_skill_loop/`）**：支持 `L1–L3` 计划期接口切换、五关行为校验与基于 SQLite WAL 的父子共享硬预算控制。
- **轨迹自适应控制与防膨胀护栏**：放行安全数学原语、前置拦截大算例高耗时候选、唤醒行为查重并引入停滞早停与盆地重启，防止算子在大规模算例上超时崩溃。
- **四层可审计记忆与离线整理（`Auto-Dream`）**：分离存储有效方案、洞察规律与反模式边界，结合去重与冷却机制抑制跨轮无效空转。
- **多问题统一与零泄漏评测底座**：同时覆盖 `CVRP`、`TSP`、`Online OBP`（严格零未来窥视）与 `Offline BPP`，强制执行开发/筛选/仓外盲测三权分立及逐种子配对统计学检验（Paired Wilcoxon + Holm–Bonferroni + 10k Bootstrap）。

---

## 核心效果（Main Results）

| 评估维度 | 代表性实证结果 |
|---|---|
| **稳定性与常规泛化（M2–M3.0）** | 跨随机种子方差压缩 `>20×`；在 `EoH-S 256`、`ABP-74`、`Set X 100` 等标准集上显著优于同协议规则。 |
| **大尺度轨迹控制（M5 · 21 路盲测）** | 120 题仓外盲测领先历史控制 **`+12.93%–+25.14%`**；在 500ms 限时 `CVRPLIB X-100` 大难题上，完成率从历史 `13%–18%` 跃升至 **`99.6%`**（DeepSeek `4/5` 种子满完赛），大幅领跑同预算 `ReEvo`（`12.3%`）与 `EoH-S`（`88.3%`）。 |
| **记忆闭环消融（M3.5 · 12 格分叉）** | `ABP-74` 全 3 颗随机种子均统计显著优于无记忆基线（**`+0.66%–+1.17%`**，`p_holm ≤ 0.0128`），且避免了朴素全量注入记忆导致的跨种子退化。 |
| **跨问题与机理可解释（M3.1 & M4）** | 打通 `TSP / Online OBP / Offline BPP` 盲测（`TSP` 显著优于 `NN+2-opt`，`p_holm=0.040`）；精确 Shapley 揭示核心算子二阶正协同 **`+3.93%`**，HRK 径向下界全库零违背。 |

> 完整多模型对比、500ms/2000ms 双预算外部大考（含 `PyVRP` / `VBS` / `AutoFolio` / `SATzilla` / `Hydra`）及详细统计检验见下方报告链接。

---

## 快速开始（Quick Start）

Windows PowerShell 安装与零成本离线冒烟（Python 3.11）：

```powershell
py -3.11 -m venv .venv-co
& .venv-co/Scripts/python.exe -m pip install -e ".[dev,eoh]"
& .venv-co/Scripts/python.exe -m agent_skill_loop smoke --problem cvrp_construct --output outputs/offline_smoke
```

在线 LLM 演化与消融实验通过环境变量配置接口与密钥（参见 [`.env.example`](.env.example)），并发调度器与各轨道入口脚本位于 `tools/`。

---

## 文档与详细报告（Documentation & Reports）

- [文档总导航](docs/README.md)：CLI 契约、协议规范、基准目录与开发约束
- [Agent 技能合同 (`SKILL.md`)](skills/algorithm-optimization/SKILL.md)：面向 Coding Agent 的标准操作规范
- [M3.5 四层记忆架构](docs/M3_5_MEMORY_SYSTEM_ARCHITECTURE.md) · [离线知识库说明](docs/knowledge_base.md)
- [M5 轨迹控制 21 路报告](experiments/milestone5_paratera/m5_trajectory_control_report.md) · [M3.5 消融报告](experiments/milestone3_5/m35_ablation_report.json) · [Track 3 430 题外部大考](experiments/baselines_2026/external_baselines_all_live_s20261124_b500.md)
- [实验与验收报告总索引](reports/README.md) · [演化轨迹交互分析页](experiments/milestone3_2/m32_evolution_trajectory.html)
