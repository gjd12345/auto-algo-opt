# 光学多后端扩展：实施方案

日期：2026-09-17

状态：实施基线。P0–P5 独立光学实现及本机验证见 [阶段验收](../extensions/optics/reports/p0_p5_acceptance_20260917.md)；本机通过不等于完整原协议复现。

P0 复核修订（2026-09-17）：统一 audit eligibility，补齐外层 controller/protocol identity 和三类 UNKNOWN 后果；保留 post-search audit，并区分预算分区与实际 effect 预留。P1 范围仅限 T1 离线适配。

关联规范：[光学多后端 TRD](optics_multibackend_trd.md)。行为、字段、错误和验收细节以 TRD 为准。

## 1. 目标与完成定义

在保留现有 CVRP、TSP、OBP 与官方 EoH 路径的前提下，使 Coding Agent 能针对 T1/T3 光学任务执行：

1. 读取冻结任务及初始处方，提交有界 Plan。
2. 生成完整处方 JSON，使用冻结物理评价器获得 online 事实。
3. 根据真实反馈继续生成，按固定 S1 规则维护搜索 incumbent。
4. 在预算内结束搜索，封存搜索状态后执行四档 audit。
5. 输出可重载的处方、完整过程证据和逐轮进化总览。

工程通过不要求找到 PASS、不要求 Q 超过历史结果。必须区分流程完成、处方有效、online 可行、本地 audit PASS、独立 verifier PASS。

现有 `tsp_2opt` 也纳入兼容保护。首版仅支持具有完整任务目录的 T1/T3；T2/T4 暂缓。

## 2. 架构决定

| 决定 | 实施要求 |
|---|---|
| 两条独立执行链 | CO 保持 `official_eoh`；光学新增 `optics_search` |
| 增量 Session 版本 | 原 `algorithm-optimization-session/v1.1` 保持不变；新 `artifact-session/v2` 使用独立数据库 |
| 一次 Session 一个 backend | backend、任务、模型、排序、采样和预算上限在初始化时冻结 |
| 原生光学候选 | 完整 JSON 处方；不要求光学方改为 Python 函数 |
| 独立光学排序 | 使用 S1 字典序；不借用 EoH 的五位小数 fitness 或按分数去重 |
| 双资产引用 | `search_incumbent` 用于探索；`best_verified_artifact` 用于最终提交选择 |
| 审计准入 | 只接收合法、完整、physics OK 且 online feasible 的可信处方；没有合格处方则队列为空 |
| 实验身份 | 生成模型与外层 controller 分别冻结；首版标 adapted_external_controller，协议说明单独 hash |
| 首版审计隔离 | 搜索阶段不运行 audit；搜索封存后进行有限审计，不再恢复该 Session 的生成 |
| 独立执行进程 | Session 控制进程不导入物理评价器；通过数据协议启动受控 Runner |
| Memory | 光学首版仅支持基于 online 证据的 insight；处方进入 Artifact Store |

概念上复用状态、预算、证据、恢复与 Memory 生命周期；首版不将旧 Session 原地改造成通用 Runtime。真正的公共代码提取安排在光学两轮 fixture 稳定之后。

### 本次主动收紧的规则

前两轮讨论要求 audit 不进入生成反馈。首版采用更容易核验的 **post-search audit**：搜索结束后才审计。搜索期间只维护审计候选队列，不暴露审计值、PASS 数、候选通过身份或审计建议。

这是本研究的实验约束。V1.4.1 原任务允许公开 audit，故报告应标明采用了更受限的信息访问方式。后续在线使用 audit 必须作为独立 treatment。

## 3. 保护现有组合优化路径

### 3.1 保护清单

- 原 CLI 默认命令、Session v1.1 schema、问题注册与 Python 资产格式。
- 固定官方 EoH commit、生成提示、父本选择、种群管理、算子与 fitness 口径。
- 原 `code_sha256`、suite/evaluator/metric 身份及旧证据读取方式。
- 原请求目的白名单、solver 账本、incumbent 比较与 Skill 资源。
- Python 3.11 的 CO 环境和既有发布物。

不向旧请求白名单加入 optics purpose；不全仓改名 `code_*`/`eoh_*`；不在旧数据库增加光学字段后宣称自然兼容。

### 3.2 分支、运行与发布隔离

实施时创建 `codex/optics-backend-v1` 独立 worktree，从明确记录的已提交基线开始。本文审查基线为 `8a37fdda128e0f4032a2ac829ccf9f7ed56fb853`，不是未来实验自动沿用的 runtime hash。

当前未提交文件属于其他工作，不复制、清理或打包进光学提交。进行中的 CO Session 留在原冻结 checkout/环境；不通过放宽身份校验让它继续使用修改后的源码。

新代码和新 Skill 采用独立顶层目录、独立发行配置。旧 Runtime 按源码及 Skill 内容计算身份：即使 API 未变，修改旧包或原 Skill 仍可能使旧 Session 不可继续。因此在集成阶段必须比较真实身份，而不能仅看版本号。

## 4. 工作包与退出门槛

| 阶段 | 任务和交付 | 退出条件 | 依赖 |
|---|---|---|---|
| P0 合同冻结 | 完成本方案、TRD、来源清单、字段与状态定义，审计隔离及预算规则 | 决策无悬空项；明确哪些为建议默认值、哪些待测量 | 无 |
| P1 T1 离线适配 | 安全资产导入、严格 JSON、online/audit wrapper、处方存储、S1 比较器 | 原入口与 wrapper 的结构/数值结果对齐；身份错误拒绝；零模型请求 | P0 |
| P2 Session fixture | v2 数据库、Supervisor、请求网关、恢复、光学 Plan/Evaluate、报告及 Memory 门禁 | 两轮完整 fixture；取消/崩溃不漏账；audit 无法影响后续生成 | P1 |
| P3 T1 真实小跑 | 冻结 pilot manifest，真实模型串行生成、反馈及最终审计 | 成功或失败都有完整终态、成本和证据；无预算追加 | P2 |
| P4 T3 适配 | 导入独立 T3 task bundle，增加任务注册和同一后端验收 | 不复用 T1 成绩/缓存；T3 多约束与审计结果对齐 | P1–P3 |
| P5 发布与集成 | 独立安装验证、CO 兼容矩阵、迁移说明；评估公共组件提取 | CO 路径无语义回归；光学证据可离线重建；已知限制公开 | P4 |

### P0：先交付哪些规范

冻结以下可版本化合同：

- `artifact-session/v2` 和 `backend-protocol/v1`。
- `optical-prescription-plan/v1`、`optical-prescription-evaluation/v1`。
- `optics-search-policy/v1`、`optics-s1-ranking/v1`。
- `optics-post-search-audit/v1`、`optical-design-artifact/v1`。
- JSON 规范化、评测身份、effect ledger 和最终提交规则。

这些是新 schema 名，不修改现有 algorithm-plan 的 schema 或文档标识。

### P1：只建设物理与资产适配

1. 导入 V1.4.1 T1 的公开环境资产，字节级校验并登记来源。
2. 参考答案、历史轨迹、作者证据与 R1 校准资产放在生成不可见的审查区域。
3. 使用原输入检查和冻结物理函数；不得修改阈值、采样、自动调焦或玻璃定义。
4. 得到可重载 `prescription.json`、online facts、audit facts 和比较记录。
5. 原 `evaluate.py` 作为独立对照入口；wrapper 的 profile 调度与原最终聚合结果对齐。
6. 测量单档/四档耗时，供 P3 预算配置使用。

P1 不需要运行新的 Session 控制器、模型或 EoH。初始处方即便不通过，也不妨碍验证评测链路；其差分 audit 是 diagnostic_audit，不代表生产队列准入或 verified 资产。原始 JSON 片段使用严格 parser/lexer 的字节 span 提取，不用 regex。

### P2：串行搜索与两轮闭环

固定父本为当前 `search_incumbent`，每次生成后 online 评测、S1 比较、形成下一候选反馈；平局保留父本。

测试至少跨两轮，以核对 Plan、incumbent、失败反馈、幂等与持久化关系。测试的两轮不成为生产运行的固定轮数：Agent 每轮申请额度，在剩余预算与轮数上限内决定继续或封存。

新增独立 `optical-design` Skill，说明新 CLI 与报告合同；首版不更新已安装的 `algorithm-optimization` Skill。二者的共用入口在 P5 再决定。

### P3：受控真实 T1 pilot

建议起始预算模板：

| 项目 | 建议值/规则 |
|---|---|
| 生成请求上限 | 6；禁止 SDK/网关隐式重试 |
| 候选上限 | 6；解析失败、重复处方也占候选尝试 |
| online 上限 | 7，包含一次初始处方评测 |
| audit 上限 | 2 个不同处方，每个四档；只在搜索封存后执行 |
| profile 总上限 | 15 = 7 online + 8 audit |
| audit 预算分区 | init 隔离8个容量单位；audit 启动时才创建4个 durable effect 预留，无合格资产则不消耗 |
| 并发 | 1 |
| Memory | 首次 pilot 显式关闭；随后独立验证 insight，不与主结果混合 |
| 修复 | 关闭；下次生成可以消费上一错误，但不启动隐藏修复调用 |
| 最大轮数 | 6，为上限；Plan 申请本轮候选数，不固定分两轮 |
| 墙钟与超时 | 根据 P1 的实际耗时确定并写入 manifest；总时限不超过任务 3600 秒 |

这些是计划默认值，P0/P1 不据此启动付费实验。P3 执行前须有对应运行授权并冻结模型、端点身份、temperature、thinking、请求超时、生成上下文上限和具体墙钟配置；已授权范围无需重复确认。

同时冻结 controller_identity/controller_contract_hash、experiment_protocol_mode 和 protocol_notes_hash；未知宿主信息如实为 null。身份不完整可以做接线验证，但不能宣称正式的 controller treatment 对照。MODEL_REQUEST UNKNOWN 关闭生成；ONLINE_PROFILE UNKNOWN 封存搜索；AUDIT_PROFILE UNKNOWN 保留 incomplete，仅在原进程确认退出后才可处理冻结队列的下一候选。具体状态见 TRD 12.1。

前序 CO 的“100 次评测预算”不转移为光学授权。pilot 不得根据中间成绩修改配置、调用上限或扩容。

### P4/P5：扩展与发布

T3 仍用同一 S1、串行搜索和 post-search audit 规则，独立 Session、TaskSpec、Memory、artifact store。R1 不作为首版默认；添加它需要单独计划并验证校准绑定。

先发布可单独安装的光学扩展，再讨论把成熟的 control-plane 实现合并。集成前明确新旧 Session 的路由和支持矩阵；禁止自动升级旧 Session 数据库。

## 5. 提交边界

1. `docs: specify versioned optics backend contracts`：仅方案/TRD及资产来源说明。
2. `feat: add offline optics task and artifact adapter`：P1、最小差分夹具。
3. `feat: add isolated artifact session lifecycle and ledger`：v2 状态、预算、恢复。
4. `feat: add sequential optics search and agent protocol`：生成、Plan/Evaluate、Skill。
5. `feat: finalize optics audit and evidence reporting`：审计队列、最终提交、重载。
6. `test: verify T1 end-to-end and CO compatibility`：fixture 和实际授权运行证据。
7. `feat: register T3 and package optics extension`：T3 与独立安装验证。

每个提交只包含本工作包的代码、文档和测试。原始私有包、凭据、输出目录和历史答案不自动纳入仓库；无许可的原始资产不随 wheel 发布。

## 6. 验证策略

遵守仓库“避免过度测试”要求。文档阶段仅检查引用、格式和合同一致性；实现阶段先 import/compile，再按受影响合同执行最小必要测试。

| 门槛 | 必须提供的证据 |
|---|---|
| G1 离线正确性 | 原入口/wrapper 对照、合法/非法 JSON、S1 决策、资产重载 |
| G2 过程正确性 | 两轮 fixture、预算对账、未知 effect 恢复、取消与失败收口 |
| G3 信息隔离 | search projection 不包含 audit，封存后不能生成，Memory 无 audit 引用 |
| G4 实际接线 | T1 模型请求和 online 反馈真实消费；失败也能形成报告 |
| G5 扩展兼容 | T3 重评、wheel 离开源码安装、CO/官方 EoH 受影响边界验证 |

精确测试场景见 TRD 的验收矩阵。没有具体失败信号时不反复扩大全仓回归；P5 涉及发布边界时执行对应安装和跨平台检查。

## 7. 交付物与发布措辞

每个光学 run 输出：冻结 manifest、Session DB、模型响应证据、逐候选 online 事实、比较记录、封存记录、审计事实、最终完整处方、SHA-256 清单和逐轮 Markdown 表。

最终报告分别列出：

- Search asset：任务绑定处方。
- Reusable experience：本次产生的受限 insight，或 none。
- Reusable algorithm：none。
- Search incumbent / best local-audit-verified artifact / final submission。
- 独立 verifier 状态：未运行则明确 `NOT_RUN`。

首版可以宣称“完成 T1/T3 原生处方的有界搜索与公开物理审计接线”。没有独立验收时，不宣称 Harbor 已通过；不宣称全波、制造认证、跨任务泛化或 EoH 官方光学复现。

## 8. 已知风险与处理

| 风险 | 处理 |
|---|---|
| 旧 Runtime/Skill hash 被新代码改变 | 独立目录、发行物和 checkout；P5 比较实际身份 |
| 多后端只改名称，内部仍依赖 EoH 字段 | v2 独立 DB、领域表及协议；新 optics 命令无 EoH 依赖 |
| 审计反馈经 Agent/Memory 回流 | 搜索封存后才审计，最终展示后不再允许继续该 Session |
| online 最优不等于 audit PASS | 双引用与明确最终提交规则；如实保留审计失败 |
| 部分审计中断造成账本失真 | assessment/profile 父子账本；未知执行量不记为零 |
| 历史答案污染 | 生成输入白名单；独立任务与审查区域；显式标记开发任务 |
| 新后端被误称为 EoH | manifest、日志和报告始终使用 `optics_search` |
| 依赖/平台未验收 | CO 保留 3.11；光学独立 3.12 环境，Linux/WSL2 为任务运行首选 |

## 9. 来源与范围说明

本方案整合前两轮架构建议及用户提供的多后端评审意见，并参考 `AIFO_optics_physics_review_20260915(1).zip` 的任务与物理证据。该包 SHA256SUMS 的341项曾在只读检查中匹配；这不等于本实现已通过物理或 Harbor 验收。实施导入时仍须重新计算身份。

来源包中的 AGENTS、README、许可和历史命令均是审查资料，不能替代用户对当前工程工作的授权。现有 CO 规范仍由原架构文档、CLI、protocol 和 sqlite-schema 文档管理，本方案不覆盖它们。
