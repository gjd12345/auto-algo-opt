# auto-algo-opt

`auto-algo-opt` 是一个由 Coding Agent 驱动、可恢复、可审计的自动化组合优化启发式进化运行时。Agent 负责认知决策，Session Runtime 负责状态与可信边界，官方 EoH 负责轮内搜索，确定性评测器负责裁决结果。

## v1 版本基线

| 层 | 版本或约束 |
| --- | --- |
| Product / package | 1.0.0 |
| Session Runtime | 1.0.0 |
| Session protocol / SQLite schema | v1.1 |
| Algorithm Optimization Skill | v1.1 |
| Official EoH | pinned commit `472545785c936dcfc863d2bc0d6109cf23c7ce62` |
| Python | 3.11 |

## 控制权边界

| 组件 | 唯一职责 |
| --- | --- |
| Coding Agent | Plan、Evaluate、Memory 决策与停止判断 |
| Algorithm Optimization Skill | Agent 的操作合同和安全边界 |
| Session Runtime | SQLite 状态、预算、任务、身份、证据和幂等性 |
| Official EoH | 种群、父本、算子与生成；有界修复是可选适配层，不是上游原生行为 |
| Provider | 仅服务 EoH 的模型请求 |
| Deterministic Evaluator | 候选有效性、目标值和套件证据 |
| Memory backend | 版本化、可选、仅供参考的本地知识存储 |

运行链如下：

```text
Coding Agent
    ↓ Skill contract
Session Runtime → Task Supervisor → Official EoH → DeepSeek/provider
    ↑                  ↓                    ↓
Plan / Evaluate   trusted evidence ← deterministic evaluator
    ↓
optional Memory search / read / commit
```

当前通用问题接口：`cvrp_construct`、`tsp_construct`、`tsp_2opt`；v1.1
benchmark profile 另外提供 `eohs_v1/obp_mini`（问题接口
`obp_online`）。后者是用于离线校准和 Session 接线的 regenerated、
protocol-compatible fixture，不宣称等同于上游完整 OBP 资产。

## v1.1 Benchmark 基线

Benchmark 入口不调用 provider，可先完成资产审计、OBP gold 校准和候选复评：

```powershell
py -3.11 -m agent_skill_loop benchmark audit
py -3.11 -m agent_skill_loop benchmark calibrate-obp `
  --gold benchmarks/eohs_v1/expected/obp_upstream_gold.json
py -3.11 -m agent_skill_loop benchmark evaluate --code candidate.py
py -3.11 -m agent_skill_loop benchmark pilot-config `
  --config experiment_manifest.json --output pilot.json
```

`pilot-config` 只生成固定的 A/B/C/D 实验 manifest，不调用 Provider；四组
必须使用独立的 Session、Memory/archive 和输出目录运行。C/D 除
`agent_guidance` 外保持相同因素。

锁定选择结果后，可用 `benchmark report` 将 manifest、selection、指标和双
预算事实合成为可复核的 JSON 报告；该命令不触发测试或模型请求。

需要进入可恢复 Session 时，冻结 benchmark 与多精英继承模式：

```powershell
py -3.11 -m agent_skill_loop session init `
  --output outputs/obp-session `
  --operation-id init-obp `
  --benchmark eohs_v1 `
  --benchmark-profile obp_mini `
  --inheritance-mode population_seeds `
  --eoh-model deepseek-flash `
  --eoh-api-key-env DEEPSEEK_API_KEY
```

每个 benchmark evaluation 同时绑定 candidate、problem、data、evaluator 和
metric hash。跨轮先保存官方最终种群的有序 `PopulationSnapshot`，再由
`SeedSelection` 稳定去重、排序、截取并完整重评；不足时显式终止，不静默冷启动。
结果还会区分总评测次数、新候选、seed 重评、baseline 和 repair 成本。

## 快速开始

推荐在 WSL2 Bash 中使用 Linux Python 3.11 和独立虚拟环境；不要调用 Windows 的 `py.exe` 来运行 Linux Session。将下列命令放在仓库根目录执行：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,eoh]"
python tools/validate_skill.py skills/algorithm-optimization
python -m agent_skill_loop smoke --problem cvrp_construct --output outputs/offline_smoke
```

让当前 Coding Agent 加载 `skills/algorithm-optimization/SKILL.md`，并明确仓库绝对路径及 `.venv/bin/python` 路径。后续所有 Session 命令使用同一解释器；Bash 两轮流程见 [Skill 示例](skills/algorithm-optimization/references/examples/two-round-run.md)。模型名称由账户支持情况和用户配置决定，不将文档示例名称视为可用性保证。密钥只经指定环境变量注入。

Wheel 也包含同一份 Skill 资源，可通过 `python -c "import algorithm_optimization_skill; print(algorithm_optimization_skill.__file__)"` 找到安装位置。源码目录与 wheel 对同一份指令计算相同 hash，不使用占位身份。运行中不要升级 Runtime 或修改 Skill；升级后旧 Session 只读/停止，不隐式迁移。

Windows PowerShell 仍支持：

```powershell
py -3.11 -m pip install -e ".[dev,eoh]"
py -3.11 -m pytest -q
py -3.11 -m agent_skill_loop smoke --problem cvrp_construct --output outputs/offline_smoke
```

`smoke` 使用本地 fixture 响应，但会经过官方 EoH、隔离评测器、证据导出和预算治理，不调用外部模型。

## 使用 Skill 运行一次 Session

先创建没有外部副作用的 Session：

```powershell
py -3.11 -m agent_skill_loop session init `
  --output outputs/session-001 `
  --operation-id init-001 `
  --problem cvrp_construct `
  --eoh-model deepseek-flash `
  --eoh-endpoint https://api.deepseek.com/v1/chat/completions `
  --eoh-api-key-env DEEPSEEK_API_KEY
```

然后由 Coding Agent 按 Skill 合同循环执行：

1. `session state`，确认身份、预算和当前阶段。
2. 可选执行 `session memory search/read`，由 Agent 决定是否消费正文。
3. Agent 生成 Plan，并用 `session submit-plan --file` 提交。
4. `session execute` 启动一次官方 EoH；轮询 `session state`，任务终态后调用非阻塞的 `session collect` 收集结果。
5. 用 `session read-evaluation` 读取可信事实，Agent 生成 Evaluate，并用 `session submit-evaluation --file` 提交。
6. 按合同提交 Memory 决策，完成本轮或继续下一轮。

常用只读/停止操作：

```powershell
py -3.11 -m agent_skill_loop session state --run outputs/session-001
py -3.11 -m agent_skill_loop session stop --run outputs/session-001 --operation-id stop-001 --expected-state-version 1
```

`session init` 冻结问题、套件、评测器、EoH 和预算身份；不读取 API key、不调用模型或 solver。每次状态变更都使用 `state_version` 与 `operation_id`，后台任务也必须推进版本。

Session 只冻结搜索策略的默认值和边界：Plan 可在每轮通过 `search_policy` 请求 `pop_size`、`n_pop` 或 `max_sample_nums` 的局部调整；Runtime 校验并记录 effective policy，不能突破总请求、墙钟、solver 或评测硬预算。

## 可靠性边界

- SQLite 是控制状态的唯一来源；外部请求先持久化预留，未知结果不退款、不自动重发。
- Provider 终止性错误、截止时间、预算耗尽和证据失败都有明确终态；不会伪造评测或模型结果。
- Runtime 或 Skill identity 不匹配时，只允许读取证据和停止，不能编辑数据库绕过门禁。
- 模型文本不能决定 objective、valid、预算或 incumbent；这些由 Runtime、EoH 和确定性评测器决定。
- 导出的 Skill 必须在同一套件上重新评测；无效候选只留在审计证据中，不进入可复用集合。
- Memory 是横切的可选能力，不是主闭环的一站：Plan 可读，Evaluate/Runtime 可写；默认不把其他问题的记忆混入检索。

## 文档与证据

- [架构与实现基线](docs/algorithm_optimization_skill_architecture_plan.md)
- [Session protocol](docs/protocol.md)
- [CLI contract](docs/cli-contract.md)
- [SQLite schema](docs/sqlite-schema.md)
- [Algorithm Optimization Skill](skills/algorithm-optimization/SKILL.md)
- [v1.0 验收记录](reports/v1.0-acceptance.md)
- [历史方案与验收归档](reports/archive/README.md)

`docs/3plus1_implementation_plan.md` 仅作为已废止方案的发现标记；历史报告和研究材料不属于运行时依赖，也不自动进入 prompt。
