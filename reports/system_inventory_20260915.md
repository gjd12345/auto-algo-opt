# 当前系统盘点与清理建议

日期：2026-09-15。审计分支：`agent-skill-loop-0908`；HEAD：`31cf9866045864a89db1fb7770cb39202503cbe8`。

## 1. 结论

系统的主要实现已经集中到 **Coding Agent + Skill + Session Runtime + 官方 EoH + 确定性评测器**；离线知识库独立构建、独立发布。当前主要问题是**文档状态滞后、实验表述与脚本能力不一致、工作区成果尚未固化、旧构建文件残留**。

本轮只提交盘点报告及扫描证据，未删除或修改现有业务代码、文档、发布包及实验资产，未调用真实 provider。

优先处理：

1. 修复知识库“工作区已修、当前发布仍错”的 Plan 启动示例，通过新 release 发布。
2. 将 A/B/C/D 的 D 组准确标为固定脚本指导实验；现有结果不足以证明外层 Agent 根据反馈自主调整策略。
3. 建立统一的当前状态入口，区分历史失败、后续成功接线、单次 pilot 和正式效果验收。
4. 固化未跟踪的实验工具与证据，再清理重复会话、旧包元数据和构建副本。
5. 恢复 Python 3.11 验证环境后，再开展运行时代码整理。

## 2. 盘点范围与限制

- 全仓 tracked 文件清点、主要目录规模、现有未跟踪文件、主要入口与依赖边界。
- `agent_skill_loop/`、`eoh_frozen/`、`knowledge_tools/`、`tools/` 共 65 个 Python 文件的 AST 语法扫描及完全相同文件检测；关键执行、实验、发布代码人工阅读。
- 23 份当前入口、合同、Skill 参考及顶层报告的本地 Markdown 链接目标检查；不含全部历史文献正文与标题锚点校验。
- 知识库 workspace/release 校验、benchmark 注册资产校验、Skill 格式校验、SQLite 文档 DDL 与实现比较。
- 本地真实接线及 A/B/C/D 的 5 个 compact bundle 完整性核对；抽查 D 组持久化 Plan/Evaluate。
- 未逐行审查全部运行时代码，未证明所有函数可达性，未重新评测候选算法，未审阅全部原始 provider transcript，未检查远程 CI。本报告不是完整功能验收或安全审计。
- 未读取 `.env` 内容。终端默认 `Get-Content` 曾错误解码中文，按 UTF-8 重读正常，因此不将显示乱码认定为文件损坏。

机器可读明细：[inventory.json](system_inventory_20260915/inventory.json)。扫描脚本：[scan.py](system_inventory_20260915/scan.py)。

## 3. 当前系统结构

```text
Coding Agent
  └─ skills/algorithm-optimization：Plan / Evaluate / Memory 操作合同
       └─ agent_skill_loop：CLI、Session、SQLite、预算、证据、恢复
            ├─ Task Supervisor → Runner → eoh_frozen → pinned 官方 EoH → Provider
            ├─ problems + evaluator → 独立子进程评测
            ├─ memory → 本地版本化 Markdown 存储
            └─ benchmark → 数据身份、archive、selection、heldout、报告

knowledge_workspace → knowledge_tools → knowledge_store/releases → current
  └─ 宿主可按固定 release 读取；不是 Session Memory 后端，也未形成 KB 实验闭环
```

| 子系统 | 主要文件 | 当前职责与边界 | 建议 |
| --- | --- | --- | --- |
| 产品与安装 | `pyproject.toml`、`README.md` | 产品版本 1.1.0；`eoh` extra 固定官方 commit `4725457…`；知识库工具不进入生产 wheel | 保留；统一环境和当前状态说明 |
| CLI | `agent_skill_loop/__main__.py` | prepare/run/smoke、skill 导入/复评、Session、benchmark；旧 workflow 仅报迁移错误 | 保留公开入口与迁移保护 |
| Session | `session_runtime.py`、`session_actions.py`、`session_contracts.py` | SQLite 状态、冻结身份、幂等操作、轮次与资源治理 | 核心保留；后续独立重构 |
| 执行与恢复 | `session_supervisor.py`、`session_runner.py`、`session_ledger.py`、`session_recovery.py`、`process_tree.py` | 进程树、请求/solver 账本、任务退出与恢复 | 保留；不能按名字相近合并删除 |
| EoH 适配 | `eoh_frozen/` 11 个 tracked 文件 | 官方引擎适配、bridge、生成合同、来源、可选有界修复、导出 | 不是废弃 EoH 副本；保留 |
| 问题与评测 | `problems/`、`evaluator.py`、`eval_worker.py` | CVRP 构造、TSP 构造、TSP 2-opt、OBP 接口；候选隔离评测 | 通用接口不等于完整 benchmark 数据已交付 |
| Memory | `memory/`、`session_memory.py` | 前者存储与检索，后者连接 Session 的消费/提交合同 | 两层不是重复实现；保留 |
| Benchmark | `agent_skill_loop/benchmark/`、`benchmarks/eohs_v1/` | 两个 OBP profile；manifest、archive、三类 selection、heldout、pilot 配置 | 保留；明确 mini 数据定位 |
| Skill | `skills/algorithm-optimization/` | 操作合同、参考说明、两轮示例、wheel 资源 | 保留；修改会影响冻结 Skill hash |
| 知识库工具 | `knowledge_tools/` 8 个 tracked 文件 | inventory/validate/build/search/read、文献采集及看板生成 | 保持与 Runtime 隔离 |
| 知识库内容 | `knowledge_workspace/` | 297 个条目、104 个 source；inventory 固定旧 ref `d6433549…` | 是版本化内容基线，不代表当前 HEAD 全部代码已入库 |
| 知识库发布 | `knowledge_store/` | 仅一个 release：`20260914-main-d6433549-kb-v0`；current 指向它 | workspace/release 双份是设计，不作为重复垃圾 |
| 工具与测试 | `tools/`、`tests/`、`.github/workflows/tests.yml` | 6 个 tracked 工具，另有 2 个未跟踪 pilot 工具；36 个 test 文件 | 固化新工具，恢复可执行测试环境 |
| 结果与历史 | `reports/`、`outputs/` | 验收、实验精简证据与完整本地 Session | 分类归档，不整目录删除 |

### 文件规模

| 目录 | tracked 文件数 |
| --- | ---: |
| agent_skill_loop | 39 |
| eoh_frozen | 11 |
| benchmarks | 15 |
| knowledge_tools | 8 |
| knowledge_workspace | 879 |
| knowledge_store | 625 |
| docs | 10 |
| reports | 95 |
| skills | 7 |
| tests | 39 |
| tools | 6 |
| 根文件与 .github | 8 |
| 合计 | 1,742 |

知识库 workspace/store 合计 1,504 个 tracked 文件，约占 86.3%。仓库文件多主要来自内容及发布资产，不代表有大量旧运行时代码。测试目录 39 个文件包含辅助文件；实际 `test_*.py` 为 kernel 24、EoH 9、knowledge 3。

## 4. 已确认问题与修订清单

优先级：P1 为影响正确使用、实验解释或后续复现的问题；P2 为文档/资产维护问题；P3 为可后置的整理。没有依据本次静态检查认定阻断全部系统的 P0。

### F01 / P1：当前知识库发布包仍包含已知错误示例

- 证据：`knowledge_workspace/plan_startup.md:9` 已用 `resolve_release()`；`knowledge_store/releases/20260914-main-d6433549-kb-v0/plan_startup.md:9` 仍是 `print(Path(...)/'current').resolve()`。
- 后者对 `print()` 返回的 `None` 调用 `resolve()`，会报错，也没有实现 `current.path` fallback。
- `validate-release` 通过只证明包符合其 manifest，不证明正文示例可运行。已有 `reports/review_c5e2d23_20260915.md:26` 记录了此缺口。
- 处理：从修正后的 workspace 构建新 release，验证实际示例及两类指针入口后切换 current；保留旧 release，不能就地改 immutable 包。

### F02 / Engineering P1 / Research-validity P0：D 组“adaptive Agent”表述超出实际脚本能力

- 证据：`tools/run_controlled_pilot.py:29` 的 `plan_for()` 仅按轮次和布尔开关选择固定方向；`operations[].mechanism` 不随评测事实改变。`feedback` 只进入身份引用。
- `evaluate_for()`（第 53 行）读取是否生成候选和证据引用，但 next_search_advice 是固定文本，没有根据分数、失败类型、弱点形成策略。
- 持久化证据 `outputs/obp_abcd_real_20260915_01/runs/D/plan_2.json` 和 `evaluation_1.json` 与此吻合。
- `tools/assemble_controlled_pilot_report.py:372` 及比较报告仍写“adaptive Agent guidance”。
- 结论：已验证 guidance 开关和反馈引用接线；不足以验证外层 Agent 的反馈驱动决策能力。不能把当前 D 组成绩解释为该能力的增益。
- 处理：保留原始实验，将 treatment 标为固定脚本指导；如开展真正 Agent 实验，另建配置与运行，记录 controller 实现/模型/版本及依赖事实的 Plan。不要改写旧事实冒充新实验。

本轮已完成 D1 纠偏：`outputs/obp_d1_router_v41_20260915/session` 的第二轮 Plan 由 Coding Agent 读取第一轮 `EvaluationFacts` 后提交，Runtime 保存 `feedback_basis`、`feedback_summary`、normalized Plan 和 submitted Evaluation；没有收集私有 chain-of-thought。第一轮生成候选与 baseline 同分，因 deadline 未形成完整 final population，第二轮被 `POPULATION_SNAPSHOT_MISSING` 安全终止。该结果验证控制链，不构成效果结论。

### F03 / P1：成功实验与新工具尚未纳入版本控制

盘点开始时 `git status --short` 仅有以下未跟踪路径，没有 tracked 修改：

- `reports/evidence/real_wiring_deepseek_20260915/`
- `reports/real_wiring_deepseek_20260915.md`
- `reports/obp_abcd_real_20260915_01_comparison.md`
- `reports/session_preflight_20260913/`
- `session-ses_f616.md`
- `tools/run_controlled_pilot.py`
- `tools/assemble_controlled_pilot_report.py`

A/B/C/D compact bundle 仍全部位于被忽略的 `outputs/`，报告还引用本机绝对路径。代码库 checkout 本身无法复现目前工作区的全部交付状态。

处理：审阅、校正脚本和结论后，将可分享精简证据与对应工具纳入版本控制；完整原始 Session 保留在本地/专门备份。不能用 `git clean` 统一清掉这些路径。

### F00 / 已关闭：审计 HEAD 的远程固化状态

- 初始审计点为 `31cf986`。只读核对远程分支得到 `8a37fdda128e0f4032a2ac829cf9f7ed56fb853`，且 `31cf986` 是该远程 HEAD 的祖先。
- 当前 audit baseline 已远程固化；记录见 `reports/d1_pilot_20260915/remote_baseline.json`。这不代表本轮工作区未跟踪变更已经 push。

### F04 / P1：当前状态入口落后于注册资产与本地证据

| 文件 | 当前问题 | 建议 |
| --- | --- | --- |
| `README.md:41,72,75` | 主要介绍 obp_mini，并链接 09-13 状态；没有当前 evolution mini 与后续真实接线入口 | 增加当前状态摘要与新 profile 说明 |
| `docs/algorithm_optimization_skill_architecture_plan.md:1257` | “当前验收状态”仍停留 09-13/14；M1 还称没有两个可执行 profile | 保留合同正文，将状态矩阵更新并链接证据 |
| `docs/experiment_plan_after_c5e2d23.md:3` | 起点仍是第二轮 seed 不足；第 4 节每组预算 40，实际 pilot 每组 100 | 保留预注册计划，新增执行偏差/完成状态，避免把 100 改回 40 |
| `reports/experiment_contracts_and_real_wiring_20260915.md` | 记录 401 失败；后续另有成功运行 | 历史事实保留，增加“后续运行”链接 |
| `reports/real_wiring_deepseek_20260915.md` | 后续步骤仍是 A/B/C/D，但本地已有四组结果 | 链接后续 pilot，说明其解释限制 |
| `agent_skill_loop/README.md:6` | 当前边界仍将 v1.0 验收列为依据之一 | 合同指向当前规范，v1.0 放到历史证据入口 |

真实运行“已存在”不等于正式效果实验“已验收”。上述更新需同时保留：mini 数据、单次运行、固定脚本指导、未验证正式增益等限制。

### F05 / 已关闭：本机无法执行项目要求的 Python 3.11 基线测试

- 初始受限沙箱中 `python --version` 为 3.14.2，`py -3.11` 不可见；默认 Python 还缺 `pygments`，因此当时未收集测试。
- 沙箱外复核发现 Python 3.11.9、pytest 9.1.1、numpy 2.4.6 和 pinned EoH 均已安装；这不是代码测试失败。
- 处理：恢复隔离 Python 3.11 和 `[dev,eoh]` 依赖后执行完整测试与 wheel/跨平台矩阵。`pyproject.toml` 的 `>=3.11` 是安装声明，而 README/CI 的 3.11 是已选验证基线；应明确其他版本的支持程度。复核已发现 Python 3.11.9、pytest、numpy 和 pinned EoH；新增修复测试及全仓结果为 **276 passed, 1 skipped**。上一版“缺失 3.11”是沙箱可见性问题，不是当前环境结论。

### F13 / Research P1：正式实验缺 execution-environment identity

- 原有 manifest 冻结 Runtime、Skill、EoH、suite 和 generation/resource contract，但没有完整记录 Python patch、解释器路径、安装包版本、硬件/线程设置和实际 provider model-router 身份。
- `tools/prepare_agent_pilot.py` 已为 D1 冻结 allowlisted `execution_environment`、源码逐文件 hash、安装 EoH commit、controller identity；不记录密钥值。
- D1 使用 `qwen/deepseek-v4.1-flash` 和 model-router endpoint，凭据只通过 `MODEL_ROUTER_API_KEY` 注入。
- 今后正式 run 缺失该身份时应拒绝启动；历史 run 不回填伪造身份。

### F06 / 已修复 / P2：heldout 工具的持久化顺序和通用性需收紧

- 历史工具曾先构造 FrozenSelection、执行 heldout，再写 selection 文件；不能据此推断已经发生 test 泄漏，但崩溃时难以独立核对顺序。
- 当前实现先用独占创建写入 selection 和 hash，再创建 `heldout-started` marker，重载并执行 heldout；重复或 hash 改动会拒绝，失败不会静默重跑。
- 同一工具第 211 行、运行工具第 81 行硬编码 `obp_evolution_mini`，不能当作任意 profile 通用工具。
- profile 仍从冻结 benchmark identity 解析，并保留 `heldout-result`；后续可继续拆分通用命令，但不再有顺序漏洞。

### F07 / P2：知识库构建文档自身有版本命名冲突

- `docs/knowledge_base.md:10` 说“新发布应在 v0 之上递增”，19 行构建命令却仍生成旧式 `...-kb-lit6`。
- 处理：示例使用明确的新 release ID；固定 ref 是来源快照，不能简单替换为 HEAD 后宣称内容已经重新审阅。

### F08 / P2：根目录保存了两份相同内容的完整会话记录

- `Knowledge_base_construct.md` 为 300,461 bytes；未跟踪的 `session-ses_f616.md` 为 300,641 bytes。
- 原始字节 hash 不同，但 CRLF→LF 后 SHA256 相同：`3eae21b7fa22f4cf0f50c3da491f0dab8c70a55435ce67afc442375e4133cd4a`。
- 内容是带用户/助手轮次的完整历史会话，不是精炼的当前规范。
- 处理：保留一份规范化历史副本到 `reports/archive/`；当前设计结论留在 `docs/kb_construct_implementation.md`/`docs/knowledge_base.md`，更新引用后去掉冗余副本。归档前保留原始来源与 hash 映射。

### F09 / P2：旧安装元数据和构建副本残留

- `eoh_rag.egg-info/PKG-INFO` 标记旧产品 `eoh-rag 0.2.0`；当前是 `agent-skill-loop 1.1.0`。
- `build/` 共 65 个文件，617,742 bytes；`build/lib` 中至少 12 个同路径 Python 文件与当前源码不同，清单见 inventory.json。
- `agent_skill_loop.egg-info/` 仍是当前包名，属于可重建元数据，不能因存在就判为旧架构。
- 处理：确认没有活动构建/环境依赖后，清理旧 egg-info 和 build；当前 egg-info 按需重建。不要将 build/lib 作为第二份源码维护。

### F10 / P2：历史与当前规范缺少清晰导航

- `docs/v11a_closure_acceptance_20260914.md` 是一次失败门禁的历史验收；放在 docs 并被当前状态直接引用，易被误读为最新结论。
- `docs/kb_construct_implementation.md` 有“本轮补齐”等无长期时效说明；`reports/v1.0-acceptance.md` 仍是根 README 的主要验收入口。
- 处理：日期型验收迁入 reports 的对应分类，原路径可短期保留重定向；实施记录标 completed/as-of，合同文档单独维护。
- `docs/3plus1_implementation_plan.md` 已正确声明 superseded 并链接历史副本，保留这个发现入口即可，无需再次删除归档正文。

### F14 / Research P1：Skill 曾未默认生成逐轮 Progress Summary

- 远程提交 `8a37fdd` 已将默认 round progress reporting 加入 Skill；本轮新增 `tools/round_progress.py`，生成并校验 public `round_progress.md` 与候选身份清单。
- D1 证据包含该摘要；后续正式 run 仍需检查实际交付，不得仅凭 Skill 文本宣称完成。

### F11 / P3：核心大文件值得拆分，但不是本次清理的删除对象

`session_runtime.py` 1,995 行、`knowledge_tools/core.py` 1,874 行、`literature.py` 1,303 行、`evaluator.py` 1,089 行。存在维护成本，但扫描未发现 65 个主要 Python 文件中有非空文件完全相同。

后续可按 schema/身份/初始化、发布/检索、文献采集/筛读、评测策略/隔离执行拆模块。必须单独提交并回归；不能把 AST 无语法错误或未被静态搜索命中理解为可以删除。

### F12 / P3：清理占位和缓存收益有限

`configs/` 为空；`.pytest_cache/` 约 33 KB；旧/当前 egg-info 合计约 11 KB。删除这些改善目录观感，但不能解决上述状态和证据问题。

`outputs/` 有 7,080 个文件、40,290,233 bytes，含本轮核对的真实实验，因此不列为统一可删缓存。

## 5. 不应误清理的内容

1. **旧 workflow 拒绝入口与相关回归测试**：它阻止误启动旧控制链，`tests/kernel/test_phase5_packaging.py` 明确验证行为；并非旧 AgentLoop 仍在运行。
2. **eoh_frozen 与官方 eoh extra**：前者为本项目适配/监督边界，后者为固定上游引擎。
3. **Memory API 与 session_memory**：存储机制和 Session 操作事务是不同职责。
4. **两个 OBP profile**：obp_mini 保留历史校准，obp_evolution_mini 用于跨轮接线；不得就地替换旧数据破坏身份。
5. **知识库 workspace 与不可变 release**：编辑源和发布快照刻意分离；文献目录中的 120 个二级问题不等于 120 个可执行 problem_id。
6. **历史失败实验与精简证据**：401、seed 不足和成功运行是不同 run，保留其来源以解释系统演进。
7. **outputs 中原始 SQLite、prompt/response 和候选代码**：compact bundle 不等价于可恢复 Session，清理前先确定恢复/复评所需资产并备份。

此外，Runtime hash 覆盖 `agent_skill_loop/` 和 `eoh_frozen/` 全部 Python 文件；Skill hash 覆盖其 Markdown/YAML 资源。即便只整理其中注释或参考说明，也可能使旧 Session 的冻结身份不匹配，应在稳定快照和新 Session 上进行。证据：`session_runtime.py:183,194`。

## 6. 当前验证与实验状态

| 检查 | 本轮结果 | 解释边界 |
| --- | --- | --- |
| tracked 文件存在性 | 1,742 个路径无缺失 | 不包含语义正确性 |
| 主要 Python AST | 65 个文件无语法错误 | Python 3.14 解析，不是 Python 3.11 全量测试 |
| 当前文档本地链接 | 扫描 23 份，无缺失相对目标；发现 6 个机器绝对链接 | 不含锚点及全部归档正文 |
| `knowledge_tools validate` | ok；297 entries / 104 sources | 3 条 unread warnings；coverage 深读为 0、摘要阅读 86，不代表全部文献已精读 |
| `validate-release` | ok；current 指向 kb-v0 | manifest SHA256 `bcf8b59581d4e0e3ac0053407e1aa1856e6cf35c879943cabefc61068171c61a`；示例错误仍存在 |
| `benchmark audit` | passed；两 profile 共 6 个资产 hash 匹配 | 未重新做算法校准与效果实验 |
| Skill 格式校验 | `Skill is valid!` | 未验证宿主实际遵循能力 |
| SQLite DDL 对比 | 文档/实现 15 个对象一致 | 内存 SQLite 比较；不是全部恢复/并发测试 |
| 真实接线 compact 包 | 16 个文件 hash 全匹配 | 不等同于第三方证明或完整 Session 可恢复 |
| A/B/C/D compact 包 | A=16、B=21、C=22、D=22，全部匹配 | 合计加接线包 97 个文件；未重新执行 provider/solver |
| 全量 pytest | 未执行到测试收集 | Python 3.11 缺失；默认 3.14 缺 pygments |
| 远程 CI / wheel / Linux-Windows parity | 未复验 | 仓库已有工作流定义，不等于最新任务已通过 |

知识库 unread warnings：`method-lit-cvrp-site-site-dependent-vrp`、`method-lit-tsp-colored-colored-traveling-salesman`、`method-lit-tsp-fuel-khuller-gas-station-refueling`。这些应保留阅读状态，不能通过清理去掉提示。

按现有报告及核对到的本地证据，真实两轮接线成功结果已存在；A/B/C/D 各一次、每组 100 次训练评测的结果也已存在，三类 heldout 报告均为 0 gap。但当前数据是 mini，且 D 为固定脚本指导，不能据此签收正式 Agent 效果、Memory/KB 增益或泛化收益。

## 7. 建议的清理顺序与验收条件

| 顺序 | 工作包 | 具体动作 | 完成条件 |
| --- | --- | --- | --- |
| 1 | 固化现状 | 保存基线和未跟踪清单；校正 pilot treatment 表述；将分享证据移至受版本管理路径并更新报告链接 | 新 checkout 能定位工具、manifest 和精简证据；原始 Session 有保留策略 |
| 2 | 收敛当前文档 | 建立 `docs/current_status.md`；README 指向它；合同、实施记录、日期型验收明确区分 | 两个 profile、失败/成功时间线、40→100 执行差异及未验收项一致 |
| 3 | 修复发布落差 | 发布含已修正 Plan 示例的新知识库版本；更新 build 示例和 current | 内容校验、发布校验、指针与启动示例通过；旧 release 不变 |
| 4 | 低风险清理 | 会话记录规范化归档去重；清理旧 egg-info、build、缓存和空占位 | 有明确路径清单；不丢原始实验；相对文档链接有效 |
| 5 | 实验工具整顿 | selection 先落盘后 heldout；明确 profile 范围；记录 controller 身份；审阅两个新工具 | fixture 验证与持久化复核通过，不能以新脚本补写旧实验行为 |
| 6 | 核心代码维护 | 在恢复的 3.11 环境和稳定快照上拆分大模块、处理经证明无用的代码 | kernel/EoH/knowledge、wheel 及平台回归通过；明确旧 Session 身份影响 |

建议目标是“一份当前状态、几份权威合同、按日期保留的证据、可重建的产物”，先解决读者会按错误说明行动的问题，再做代码结构美化。

## 8. 本轮交付

- 本报告：盘点、已确认问题、保留清单、清理顺序与验证边界。
- `reports/system_inventory_20260915/inventory.json`：规模、重复会话 hash、构建差异、文档链接、证据包校验结果。
- `reports/system_inventory_20260915/scan.py`：只读扫描及生成本目录 JSON 的复核脚本。

本报告列出的修订、归档、删除和新发布均为后续工作，尚未执行。
