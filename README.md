# auto-algo-opt

面向**组合优化自动启发式算法设计**的自主研究代理与闭环演化框架。项目将多层级求解接口切换、冻结官方 EoH 演化内核、进化轨迹自适应控制与四层可审计记忆闭环整合为统一底座，支持 **带容量车辆路径（CVRP）**、**旅行商（TSP）**、**在线一维装箱（Online OBP）**与**离线一维装箱（Offline BPP）**。

---

## 核心功能（Core Features）

```mermaid
flowchart LR
    B["标准基准与仓外盲测隔离\n开发集 · 选优集 · 密封盲测"] --> RA["自主研究代理与多层级求解接口\n逐点构造 / 并行合并 / 破坏重建"]
    RA --> EOH["冻结 EoH 演化内核\n父子共享硬请求预算"]
    EOH --> CTRL["进化轨迹防膨胀护栏\n五关校验 · 查重 · 停滞重启"]
    CTRL <--> MEM["四层记忆与离线整理\n策略 / 洞察 / 禁忌 + 配对检验"]
```

- **多层级求解接口与诊断驱动研究代理（`research_agent/` + `agent_skill_loop/`）**：支持在计划期自主切换“单步逐点构造、静态/动态并行合并、邻域破坏–重建”多层求解框架，内置五关行为因果校验与基于 SQLite WAL 的共享硬预算控制。
- **进化轨迹防膨胀护栏与自适应控制**：放行安全纯数值数学原语、前置拦截大算例高耗时候选、唤醒行为等价查重并引入停滞早停与盆地重启，避免算子在大规模算例上因循环膨胀触发超时。
- **四层可审计记忆与离线整理（`Auto-Dream`）**：分离存储有效策略、洞察规律与带适用边界的反模式禁忌，配合多样性检索与冷却机制抑制跨轮无效空转。
- **多问题统一与防泄漏评测底座**：同时覆盖 `CVRP`、`TSP`、`Online OBP`（严格禁止未来物品窥视）与 `Offline BPP`，强制执行开发/筛选/仓外盲测三权分立及逐种子配对非参数检验（Wilcoxon + Holm–Bonferroni + 10k Bootstrap）。

---

## 评测基准、评价标准与核心效果（Benchmarks & Main Results）

- **评测基准**：包含与搜索过程物理隔离的多规模仓外盲测集（120 题，覆盖 50–200 客户），以及 **430 道国际公开带容量车辆路径标准真题**——多分布测试集 `EoH-S`（256 题）、经典中小规模库 `CVRPLIB Set A/B/P`（74 题）、最高近千客户的超大规模库 `CVRPLIB Set X`（100 题），并辅以旅行商（`TSPLIB`）与一维装箱（`BPPLib`）公开标准库。
- **评价标准**：在严格单题墙钟计算时限（`25 ms / 500 ms / 2000 ms`）内，衡量算法按时输出合法可行解的**完成率**、**平均总路径长度**（或相对参考最优解的**百分比间隙**，越低越好），以及多颗独立随机种子重跑的**跨种子标准差**（衡量搜索稳定性）。

| 评估维度 | 核心实证效果 |
|---|---|
| **演化稳定性与常规泛化** | 引入诊断驱动研究代理与多层级求解接口后，在 120 题仓外盲测（`500 ms` 时限）上将多随机种子重跑的**跨种子标准差压缩逾 `20` 倍**（对比无工具与纯文本反思基线）；在 430 题国际公开真题上，单条冻结启发式的平均相对最优解间隙压至 **`4.06%–5.66%`**。 |
| **大规模算例防超时与轨迹控制** | 加入安全数学原语放行、大算例耗时前置筛查与停滞重启后，在 120 题仓外盲测上较未加控制的历史演化算子缩短路径 **`12.93%–25.14%`**；在 `500 ms` 紧预算的千客户级 `CVRPLIB Set X`（100 题）上，按时合法完成率从历史 `13%–18%` 跃升至 **`99.6%`**（`DeepSeek-V4.1-Flash` 5 颗种子中 4 颗 `100%` 满完赛），显著高于同等演化预算下的 `ReEvo`（`12.3%`）与 `EoH-S`（`88.3%`）。 |
| **跨轮记忆闭环与离线整理** | 在 74 题经典 `CVRPLIB Set A/B/P` 上，经离线蒸馏与去重冷却的四层记忆闭环在全部 3 颗随机种子上均统计显著优于无记忆基线（平均路程缩短 **`0.66%–1.17%`**，Holm–Bonferroni 校正后 $p \le 0.0128$），并避免了朴素全量注入记忆带来的跨种子退化。 |
| **跨问题泛化与数学机理可解释性** | 同一框架扩展至旅行商（72 题独立盲测显著优于经典“最近邻 + 2-opt”，路程缩短 **`0.92%`**，$p_{\text{Holm}}=0.040$）及在线/离线一维装箱；精确 Shapley 合作博弈拆解揭示核心算子组件间存在 **`+3.93%`** 的二阶正向协同效应，异质需求径向运输下界全库零违背。 |

> 不同大模型家族（含 `Qwen4-Max` 大尺度超时边界）及 `500 ms / 2000 ms` 双预算下与 `PyVRP`、`AutoFolio`、`SATzilla`、`Hydra` 等经典基线的完整统计对照见下方报告链接。

---

## 快速开始（Quick Start）

Windows PowerShell 安装与零成本离线冒烟（Python 3.11）：

```powershell
py -3.11 -m venv .venv-co
& .venv-co/Scripts/python.exe -m pip install -e ".[dev,eoh]"
& .venv-co/Scripts/python.exe -m agent_skill_loop smoke --problem cvrp_construct --output outputs/offline_smoke
```

在线大模型演化与消融实验通过环境变量配置接口与密钥（参见 [`.env.example`](.env.example)），并发调度器与各实验入口脚本位于 `tools/`。

---

## 文档与详细报告（Documentation & Reports）

- [文档总导航](docs/README.md)：命令行契约、评测协议、基准目录与开发约束
- [Agent 技能操作合同 (`SKILL.md`)](skills/algorithm-optimization/SKILL.md)：面向智能体的标准运行规范
- [四层记忆与知识库闭环架构说明](docs/M3_5_MEMORY_SYSTEM_ARCHITECTURE.md) · [离线知识库发布机制](docs/knowledge_base.md)
- [进化轨迹控制 21 路盲测报告](experiments/milestone5_paratera/m5_trajectory_control_report.md) · [记忆闭环 12 格分叉消融报告](experiments/milestone3_5/m35_ablation_report.json) · [430 题国际外部基线双预算大考](experiments/baselines_2026/external_baselines_all_live_s20261124_b500.md)
- [实验与验收报告总索引](reports/README.md) · [大预算演化轨迹交互分析页](experiments/milestone3_2/m32_evolution_trajectory.html)
