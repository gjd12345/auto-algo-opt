# auto-algo-opt

Coding Agent 驱动的优化框架：**Agent 规划与解释，Runtime 管理状态和预算，确定性评测器裁决结果。**
目前有两条独立运行路线；光学扩展没有替换官方 EoH，也不改变原 CO Session。

| 路线 | 优化对象 | 执行器 | Python / 包 | Skill |
|---|---|---|---|---|
| 组合优化（CO） | 可重载的 Python 启发式代码 | 固定版本官方 EoH，轮内种群演化 | 3.11 / agent-skill-loop 1.1.0 | [algorithm-optimization](skills/algorithm-optimization/SKILL.md) |
| 光学处方 | 原生 prescription.json | 串行生成处方＋隔离物理评测，不经过 EoH | 3.12 / optics-artifact-session 0.2.0 | [optical-design](extensions/optics/skills/optical-design/SKILL.md) |

## 控制权与闭环

1. 宿主 Coding Agent 根据问题合同、可信反馈和可选 Memory 制定 Plan。
2. Runtime 校验并冻结允许的输入，预留请求/评测预算，启动执行任务。
3. 执行器生成候选，确定性评测器返回可核验事实。
4. Agent 读取事实、提交 Evaluate，决定是否写 insight、继续或停止。

Memory 是横切能力，不是闭环中必经的一站。配置开启不代表实际写入或消费。
模型不能决定 objective、可行性、预算或 incumbent；Runtime 不自动推荐算法族。
每轮输出请求、评测、候选、incumbent 和 Memory 的事实表，缺失值保持未知。

## 组合优化：快速开始

使用独立 Python 3.11 环境。在仓库根目录运行：

```powershell
py -3.11 -m venv .venv-co
& .venv-co/Scripts/python.exe -m pip install -e ".[dev,eoh]"
& .venv-co/Scripts/python.exe tools/validate_skill.py skills/algorithm-optimization
& .venv-co/Scripts/python.exe -m agent_skill_loop smoke --problem cvrp_construct --output outputs/offline_smoke
```

Linux/WSL 使用 `python3.11 -m venv .venv-co` 和 `.venv-co/bin/python`，
不要混用Windows解释器。输出目录需为新目录。
smoke 使用fixture，不调用外部模型，但会运行官方EoH及隔离评测。

- 通用接口：cvrp_construct、tsp_construct、tsp_2opt。
- OBP benchmark 接口：obp_online；已注册 obp_mini 与 obp_evolution_mini。
- EoH固定commit：472545785c936dcfc863d2bc0d6109cf23c7ce62。
- 可选有界修复属于本仓库适配层，不是上游EoH公开插件。

创建真实 Session 的示例（init本身不调用模型）：

```powershell
& .venv-co/Scripts/python.exe -m agent_skill_loop session init `
  --output outputs/co-session-001 `
  --operation-id init-001 `
  --problem cvrp_construct `
  --eoh-model YOUR_MODEL `
  --eoh-endpoint https://YOUR_PROVIDER/v1/chat/completions `
  --eoh-api-key-env OPTIMIZATION_API_KEY
```

密钥只通过所指定的环境变量提供；模型和endpoint必须采用实际已授权配置。
让宿主加载CO Skill，按以下合同完成闭环：

```text
state → 可选 memory search/read → submit-plan → execute
      → state/collect → read-evaluation → submit-evaluation
      → Memory决策 → finish-round
```

变更动作使用当前state_version与唯一operation_id；不确定是否成功时复用同一ID/输入。
Plan可在冻结边界内调整逐轮pop_size/n_pop/max_sample_nums，不能突破全局预算。
完整操作见 [CLI合同](docs/cli-contract.md)、[协议](docs/protocol.md) 和
[两轮示例](skills/algorithm-optimization/references/examples/two-round-run.md)。

## Benchmark：先校准，再谈效果

```powershell
& .venv-co/Scripts/python.exe -m agent_skill_loop benchmark audit
& .venv-co/Scripts/python.exe -m agent_skill_loop benchmark calibrate-obp --gold benchmarks/eohs_v1/expected/obp_upstream_gold.json
& .venv-co/Scripts/python.exe -m agent_skill_loop benchmark --help
```

mini数据用于协议兼容、校准和接线，不宣称完整EoH-S exact reproduction。
训练选择必须锁定后才能评估heldout；test不反馈训练、Memory或incumbent。
种群继承先保留原始PopulationSnapshot，再派生SeedSelection，按身份完整重评；
后续轮seed不足显式终止，不静默改为冷启动。

总评测、生成候选、seed、baseline、repair须分项计账。
四组受控实验的fixture、真实pilot与正式重复实验应分别报告，不能相互替代。
参见 [OBP数据说明](docs/obp_evolution_mini.md) 和 [报告索引](reports/README.md)。

## 光学：独立安装与处方优化

光学任务生成JSON处方，不生成CO风格的select_next_node，也不使用EoH搜索。
不要升级或复用CO虚拟环境：

```powershell
py -3.12 -m venv .venv-optics
& .venv-optics/Scripts/python.exe -m pip install ./extensions/optics
& .venv-optics/Scripts/python.exe -m optics_backend --help
& .venv-optics/Scripts/python.exe -m artifact_session --help
```

需用户提供已审计的项目方task archive；原始资产及密钥不随wheel/Git分发。
支持T1 singlet、T3 triplet。按 [扩展说明](extensions/optics/README.md) 导入task bundle，
准备冻结配置并初始化：

```text
python -m artifact_session init --run <new-run-directory> --file <config.json>
python -m artifact_session state --run <run-directory>
```

加载独立optical-design Skill执行Plan/生成/online/Evaluate闭环。
S1以可行性和约束违反优先，再比较Q；合法但不可行不等于解析无效。
搜索封存后才执行固定队列的四档audit，audit不能回流同run的搜索或Memory。
独立verifier另行运行，不能用local audit PASS冒充认证。

最近T1实验：Luna外层、DeepSeek生成，9轮170个候选，最佳可行online Q=0.5552282993；
实际195/500物理profile上限，Agent主动结束。5份audit PASS，独立verifier22/22通过。
这是单run结果，Memory开启但未消费，存在61.2%的重复生成；
不证明最优或统计显著性。见 [实验摘要](reports/optics_t1_luna_20260917.md)。

光学验证环境为Windows Python3.12.11。Linux Python3.12.14尚未验收，T3仅有离线差分。
verifier保持independent_wavefront_verified=false，不宣称独立波前认证。

## 安全、恢复与产物

- SQLite是控制状态权威；effect先预留，UNKNOWN不能当零成本或自动重放。
- Runtime/Skill身份不符时不绕过门禁；升级后使用新Session，旧证据保留只读。
- 恢复须核验完整落盘事实、评测身份和账本，且确认相关进程已退出。
- 固定评测输入、规则、阈值不由模型修改；失败与未改善均如实记录。
- 密钥仅通过环境变量；原始私有运行目录不自动提交Git。
- hash链证明可信宿主内一致性，不是数字签名；子进程隔离不是恶意评测器沙箱。

| 目录 | 用途 / 清理原则 |
|---|---|
| agent_skill_loop/、eoh_frozen/ | CO生产实现 |
| extensions/optics/ | 独立光学包、Skill、测试及验收说明 |
| benchmarks/ | 冻结资产与gold，不作为临时产物删除 |
| outputs/、extensions/optics/.local/ | 本地运行数据（gitignored）；删除前核对是否仍为证据来源 |
| reports/evidence/ | 可发布compact evidence，保持清单/hash和路径 |
| reports/archive/ | 历史报告、预注册、截图与研究资料；不自动进入prompt |
| knowledge_workspace/、knowledge_store/ | 离线知识库与不可变release，不等于Session Memory |

本轮未删除历史证据；旧build与eoh_rag元数据移至仓库外可恢复备份。
没有修改运行中的Skill或Runtime。无需在文档整理后重跑付费实验。

## 文档导航

- [当前文档索引](docs/README.md)
- [报告及证据索引](reports/README.md)
- [CO架构与benchmark实施计划](docs/algorithm_optimization_skill_architecture_plan.md)
- [光学实施方案](docs/optics_multibackend_implementation_plan.md) / [TRD](docs/optics_multibackend_trd.md)
- [光学阶段验收与恢复补充](extensions/optics/reports/p0_p5_acceptance_20260917.md)
- [离线知识库](docs/knowledge_base.md)
- [历史归档](reports/archive/README.md)

计划中的阶段不等于已完成；以对应提交、环境和原始证据的验收记录为准。
