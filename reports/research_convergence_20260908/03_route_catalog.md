# 仓库科研路线总目录

基于 2026-09-08 当前工作树，Git 基线 `c8cb66c`。这里按“改变什么对象、回答什么问题”归并路线，同时保留细分实验和历史阶段；同一思路的 v1/v2、续跑、失败诊断不冒充独立科研成果。

完整文件快照：[04_repository_inventory.csv](04_repository_inventory.csv)。该清单覆盖审阅开始时 957 个文件，包括 941 个 tracked；逐文件记录内容 hash 和分工范围。阅读范围和原始证据缺口见 [检索报告](01_retrieval_report.md)。

## 1. 路线地图与处理决定

“保留”指可供新主线复用的接口或知识，不意味着恢复旧实验；“历史”指可复现/可追溯资产；“提案”不算已运行。

按用户后续修订，具体实施以[执行计划v3](02_execution_plan.md)为准。表内历史知识保留仅指历史快照/人工查阅，不是新prompt输入。首版只从基线或用户显式指定的一个父skill开始；父代码在新套件重评。新内核重写loop和journal，旧分支冻结，删除仅发生在新分支，四组内核测试同步保护抽取过程。完成定义是生成→独立评测→反馈被后续prompt消费→预算停止；全失败可跑通，明确no_valid_candidate。fixture只证明接线，通过后再授权真API；不以算法提升或产生合法候选作为闭环完成门槛。

| ID | 路线与不能遗漏的分支 | 仓内证据入口（根目录相对路径） | 已有认识与边界 | 新主线处理 |
|---|---|---|---|---|
| R01 | Go 业务求解：InsertShips 动态派船/路由、SA 基线网格、EOH 对照；Go bin_packing_online、knapsack、mixer_split | `go_solver/`；`Agent_EOH/eoh/src/eoh/examples/user_insertships_go/`；`evidence/go_eoh_rag_20260705/`；`eoh_rag_workspace/problems/` | 有求解器、例题和小规模 RAG/无RAG报告；不是新 FME 三问题评测体系。Go 输出文本与通用适配器期待 JSON 存在接口差异 | 历史；以后需要业务迁移时单独接适配器 |
| R02 | 官方 EoH thought/code 进化、i1/e1/e2/m1/m2、population、确认门；Agent_EOH 内 EOH/AEL/LocalSearch 变体 | `official_eoh/eoh/src/eoh/eoh/`；`Agent_EOH/eoh/src/eoh/methods/` | 两套引擎/问题注册并存。方法选择器中的名字不代表对应目录均已实现；不能把字符串 reevo/funsearch 当现成实现 | 只复用现有生成适配器与可执行接口 |
| R03 | RAG 关键词、结果感知重排、种群特征四臂；数据收集、outcome backfill、TSP D臂续跑 | `eoh_rag/rag/`；`eoh_rag_workspace/reports/ablation_4arm/`、`reports/outcomes/` | 历史 CVRP C 对 A 的中位目标改善约6%，TSP约0.8%；D臂原始实验 pop_n=0，不能据此判断种群特征无效。小样本报告中的“significant”不自动等于统计显著 | 仅历史归档；首版不接RAG，旧文本/失败知识不进入prompt |
| R04 | Phase4b LLM rerank/full、F1温度/F2宽池/F3特征比例、BP adaptive/warm、M3算子筛查与确认 | `experiments/manifests/phase4b_*`（均在 workspace）；`bp_m3_*`；`m3_*`；`eoh_rag_workspace/reports/phase4b/` | 模型/配置/算子和暖启动同时变化，结果按各协议读；不能归为同一条普适收益 | 历史消融，不默认增加重排调用 |
| R05 | 多代进化、共享池/Island Model、605-run精英、历史top6继承池 | `evidence/final_batch_20260630/`；`eoh_rag_workspace/reports/island_model_final_report.md`；`scripts/launch_island.sh` | 冻结605次，最优值有存档；多运行取最优、共享池和预算差异不能作新单轮因果证据 | 保留算法资产，首版单进程小预算 |
| R06 | BP 最优代码可解释性、same-size reservation、精英结构相似度、代码同源与冗余 | `docs/TRD_bp_interpretability.md`；`evidence/bp_interpretability/`；历史阶段A | 提出可解释结构与相似性证据；词法/源码相似不等于同功能或新机制 | 保存研究知识，不设解释正确性前置门 |
| R07 | BP Q3 pure/generic/answer，harmonic+residual双卡、API-only/sham对照、融合语义确认、单卡组件归因 | `reports/strategy_experiments/q3_v2/`、`q3_card_components/`；`eoh_rag_workspace/experiments/strategies/q3_mechanism/` | Q3 answer 对 pure 7胜/3负，方向性支持；20个组件坐标12有效8失败，只支持互补或上下文交互，不证明加性协同 | 保留对照经验，不要求先复跑Q3 |
| R08 | BP/TSP/CVRP 跨问题抽象策略迁移：local_only/mixed_abstract；抽象卡映射 | `reports/strategy_experiments/cross_problem_transfer/`；`strategies/abstract_strategies.json`、`transfer_card_map.json` | 9/15完整配对，TSP 0/5，inconclusive；静态跨问题提示不是自主迁移 | 暂缓，首版问题内skill |
| R09 | BP legacy/objective-aware、robust/scale-balanced/scale-structured、aggregate/confirmation-aware反馈 | `eoh_rag_workspace/experiments/manifests/bp_*feedback*`；历史诊断摘要 | 区分反馈形式改变、开发目标改变与确认数据影响；proxy胜出未必新分布有效 | 保留反馈设计经验；新首版仅真实数值与错误 |
| R10 | BP gate-only、跨分布gate/local refine、agent v2/dual/gate候选、HiFo泛化 | `experiments/assets/bp_online_agent_discovery_*.json`（workspace）；`bp_*generalization_confirm*`；`bp_confirmation_gate_agent_hifo_v1.json` | 部分资产标为dev confirmed或large confirmed，部分仍proxy/optional seed；HiFo是范围扩展，不把所有候选混称泛化成功 | 历史；不移植多层confirmation为工程门槛 |
| R11 | BP 单常数 n1 邻域与 n2 双常数补偿；离线数值变异 | `bp_numeric_neighborhood_proxy_v1.json`、`bp_numeric_pair_compensation_proxy_v1.json`；官方 `evolution.py` | 搜索代码常数的路线，区别于LLM新结构；重复数值扰动不自动形成新机制 | 作为以后无模型基线，不冒充LLM skill生成 |
| R12 | TSP 搜索计划控制器，预算/原语白名单，seed diversity、agent memory、feedback RAG、objective-aware | `eoh_rag/search_control/tsp_controller.py`；`official_eoh/examples/tsp_search_controller/`；`tsp_search_controller_*` manifests/assets | 优化的是搜索计划，不是construct函数；存在预算合同修订和跨规模确认，不能与construct成绩直接拼接 | 历史；保留预算思想，不接入首版 |
| R13 | TSP 质量/速度双档案、合成与运行探针、选择器、双槽/三槽、多样性/功能冗余、Core12/TSPLIB验证 | `agent_records/archive/obsidian_20260718/` 阶段AE–BR等；`scripts/`对应分析/确认程序 | 大量局部探针与条件化证据；包含评估器成本、影子评估器修复、串行复核。逐阶段见后附表，不能将全部称为成功selector | 历史资产，首版无需portfolio |
| R14 | TSP 固定修复与局部搜索：2-opt、近邻引导、确定性ILS、relocation、Or-opt-2/3、全邻域盆地重启、受限3-opt | 同档案阶段BR–CE；`scripts/`局部搜索/外部确认程序；`tsp_controller.py` | 某些大实例改善来自外部固定优化器，不等于模型发现或选择器收益；时间成本与可行性必须计入 | 保存可执行原语，以后按问题单独复用 |
| R15 | CVRP n1/n2与BP数值机制可迁移性，confirmed savings/regret，密度结构、需求方差、多环境反馈/e1e2、fresh诊断与环境冲突 | `eoh_rag_workspace/experiments/strategies/contexts/cvrp_*`；`cvrp_*diagnostic*`；`cvrp_core_final_report_v1.json` | 已有明确失效的结构和开发域记忆；新诊断下密度bonus与需求方差未建立稳健收益。历史confirmed父本不保证新合成域优势 | 选择CVRP接口；首版从可复现简单基线起步，历史父本可显式导入 |
| R16 | CVRP 专家组合可学性、KNN、pairwise unweighted/cost-weighted、abstain/tie backup、portfolio complementarity | `eoh_rag/experiments/pairwise_selector.py`、`portfolio_feedback.py`及selector相关脚本；`cvrp_pairwise_*`；7月19日handoffs | development-only；事后oracle空间和可训练选择器收益不同；4个专家不意味着4个独立可靠机制 | 历史，暂不加入元选择层 |
| R17 | CVRP LLM expert router、paired gate、DeepSeek fallback、ReEvo-inspired memory v2 | `official_eoh/examples/cvrp_expert_router/`；`cvrp_expert_router_*`、`cvrp_router_reevo_inspired_v2.json`；handoffs | 有proxy与门禁，v2提案状态不能视为已完成；ReEvo-inspired文字记忆不等于完整官方ReEvo | 暂缓 |
| R18 | TOCC轨迹条件控制：诊断、选卡、LLM proposer、guard/gatekeeper、mini manifest、query/history审计、训练数据准备 | `eoh_rag/tocc/`；`eoh_rag/experiments/training/`；`eoh_rag_workspace/reports/auto_experiment_reports/tocc_*` | 已有规则诊断与卡片控制路径，连到旧batch；不能把训练准备或实验名当作已部署的学习控制器 | 历史；保留有界反馈思想 |
| R19 | 早期 BP FME 机制生态/主动反例，descriptor校准，action-order v2 | `bp_falsifiable_mechanism_ecology_creation_pilot_v1.json`；`bp_fme_action_order_v2_proposal.json`；7月23日handoffs | 机制门与质量门分离；历史FME有效候选率低于控制；action-order v2提案有未批准状态 | 记录失败边界，不继续补跑 |
| R20 | BP order-regime 顺序敏感性：相同multiset不同order、近似平局诊断、两候选比较、可选诊断工具、ORF-001..005修订 | `eoh_rag/fme/order_regime_feedback.py`、`order_regime_integration.py`、`order_regime_memory.py`；7月23日handoffs | 固定3 regimes×2 multisets、完整摘要与身份绑定；属于BP开发诊断，当前没有贯通成通用自主skill | 历史/可选诊断，CVRP首版关闭 |
| R21 | D0–D32深度优先恢复：身份与因果链、反证驱动repair、行为档案、局部见证到全局策略的可组合性 | `agent_records/handoffs/2026-08-02_130606-mainline_recovery-d0_d32_curated.agent.json`；`kb_router_v4.json` | D1历史action链、D2动作改变不等于质量；D3–7新颖性/暴露未立；D8–32局部干预未组合成端到端合法策略。仅精选资产恢复，原完整实验不在当前树 | 保留证据身份/错误经验，不恢复被排除模块 |
| R22 | Refactor0830单一FME组合根、三问题适配、algorithm/counterexample/mechanism档案、analysis/question stack、Potential | `eoh_rag/fme/mainline.py`、`research_loop.py`、`archives.py`、`analysis.py`、`potential.py`；Phase1–3审计 | 核心编排与记录存在；决策是预设规则，当前没有控制器自进化；有些行为描述字段为固定范围近似 | 抽取生成/评测能力，重写loop/journal；不导入旧FME包 |
| R23 | RQ1–RQ4冻结历史离线重放 | `eoh_rag_workspace/reports/refactor0830_phase4/rq1_rq4_offline_replay.json` | RQ1机制门通过、质量负向；RQ2问题相关且缺随机控制；RQ3不确定；RQ4无在线模型对照。不是新在线效果 | 只读参考 |
| R24 | RQ1–RQ4新在线矩阵：scalar/passive/active、none/relevant/shuffled历史、abstract/shuffled abstract、Flash/Pro；provider v2–v7 | `eoh_rag_workspace/reports/refactor0830_online_review/`；v7 result review；6个online manifests | v7 81坐标执行完成/按规则停滞停止，没有稳定主动/迁移/大模型收益；v3–v6协议/传输中断与独立cohort不合并为一个成功样本 | 历史冻结，首版不默认启动矩阵 |
| R25 | RQ1b行为约束被动分析：CVRP A/B/C，同代码诊断、预测校准、Target/Potential/Chain；v1中断、v2持久请求、v2同队列续跑 | `eoh_rag/fme/rq1b*.py`、`behavior_analysis.py`、`behavior_probes.py`；calibrations与contracts | 最新完整v2 Integrity通过，Behavior/Target/Search/Chain未通过；809 HTTP与384候选不是同一预算量。不是离线replay，尽管续跑包含精确历史回放 | 终止扩展，保留追溯机制 |
| R26 | Phase6新领域：JSSP优先候选，MaxCut与Knapsack合同 | `agent_records/contracts/phase6_generalization_contract_v1.json`；`eoh_rag_workspace/reports/refactor0830_phase6/` | 三领域有描述/合同，JSSP evaluator、baseline和split尚未实现。与早期Go knapsack不是同一完成状态 | 提案，首版不做 |
| R27 | 光学设计迁移：外层进化优化策略，内层团队数值优化/仿真，固定MTF/波前/约束验收 | 本地未跟踪 `reports/optical_transfer/.build/create.mjs`与两份output PPTX | 演示/迁移方案；没有仓内光学注册、仿真或结果，组合优化成绩不能外推为光学收益 | 列入全量清单，明确未实施 |
| R28 | 研究基础设施：PoolAPI/RunTracker/hooks、失败/算子记忆、知识路由、资产清单、评测schema、证据隔离与迁移 | `docs/specs/`；`eoh_rag/experiments/`；`agent_records/inventories/`、`knowledge/`；`docs/migrations/` | 支撑性模块不是独立科研效果；旧资产清单的“formal”时态不能覆盖新mainline registry | 选用必要组件，不再加第二套总框架 |
| R29 | SmartOperator代码Agent：定向变异、编译自修复、失败记忆、fast/balanced/robust模板、BoundedReactPlanner | `eoh_rag/operator/`；`eoh_rag/strategy_router.py`；`solver_adapter/` | 是已有的受限生成/执行/失败修订原型，主要面向Go/InsertShips；不能无适配移用模板到CVRP Python | 仅参考失败闭环设计，不导入新内核或注入历史失败记忆 |
| R30 | InsertShips ReAct研究Agent：计划、调用进化工具、分析、报告与web search | `Agent_EOH/eoh/src/eoh/examples/user_insertships_go/v2_agent/` | 已有自主工具编排尝试；依赖Go、模型和工具，方法名/工具名不代表每条路径都可用 | 历史，不给首版追加浏览器与联网研究工具 |
| R31 | 24小时自主科研流程与外部知识库协作：读状态、避免重复启动、唯一下一步、API受阻转离线、按结果转向、交接 | `docs/diagrams/obsidian_20260718/自主科研循环_2026-07-13_235608/24小时自主科研循环.drawio`；`agent_records/handoffs/` | 研究工作流设计/历史交接，不是已经证明能自主形成新算法的控制器；其TSP阶段性主线不覆盖8月FME与当前需求 | 保留工作方法；首版执行目标仍为有限算法skill循环 |

## 2. 按问题重新索引

| 问题/对象 | 路线 |
|---|---|
| BP / online bin packing | R02–R11、R18–R20、R22–R25；R01另有Go实现 |
| TSP构造/搜索计划/大规模修复 | R02–R05、R08、R12–R14、R18、R22–R24 |
| CVRP构造/专家选择 | R02–R05、R08、R15–R17、R21–R25 |
| InsertShips及Go业务问题 | R01、R02的Go变体、R29、R30 |
| 新领域仅合同 | R26：MaxCut、Knapsack、JSSP |
| 光学仅迁移设计 | R27 |
| 跨问题基础设施/科研编排 | R18、R21、R22、R28 |

因此“现有仓库支持几个问题”没有一个脱离入口的答案：新FME有3个真实评测问题，旧官方轨道还包含TSP controller/CVRP router，Go注册还有4类业务问题，Phase6和光学只是拟接入领域。

## 3. 特别容易混淆的结论

- Q3 的正向结果只属于其冻结的BP卡片实验，不是跨问题迁移证据。
- TSP 外部手写修复原语的效果，不是模型自主发明同样原语的证据。
- CVRP oracle portfolio 空间不等于可部署选择器收益。
- active controller、passive reflection、行为约束预测、实际错误反馈是不同干预。
- algorithm archive、RAG card、mechanism claim与可重载skill不是同一对象。
- D0–D32的精选恢复记录是历史知识来源，不代表所有旧单次实验脚本还在仓内。
- RQ1b v2 resume是同cohort续跑；v1不能并入v2提高样本量。
- 本次新方案选择简单CVRP基线是为了证明运行能力，不否认历史savings/regret资产；未重评前不把旧分数写到新skill。

## 4. 全部实验manifest索引

下表所有文件均位于 `eoh_rag_workspace/experiments/manifests/`；每个文件恰好列一次。93个文件包含实验、诊断、注册表、提案和report合同，**不是93个已完成实验**。RQ1b两版归入在线行为分析路线，不能因为有resume/replay部件就称离线实验。

| 编号 | manifest | 主路线 |
|---:|---|---|
| 1 | `adaptive_bp_online.json` | R04 |
| 2 | `adaptive_bp_warm.json` | R04 |
| 3 | `bp_ablation_cards_q3_proxy.json` | R07 |
| 4 | `bp_ablation_cards_q3.json` | R07 |
| 5 | `bp_ablation_cards.json` | R03 |
| 6 | `bp_ablation_preflight.json` | R03 |
| 7 | `bp_agent_v2_generalization_confirm_v1.json` | R10 |
| 8 | `bp_card_component_q3.json` | R07 |
| 9 | `bp_confirmation_feedback_proxy_diagnostic_v1.json` | R09 |
| 10 | `bp_confirmation_feedback_proxy_v1.json` | R09 |
| 11 | `bp_confirmation_gate_agent_generalization_confirm_v1.json` | R10 |
| 12 | `bp_confirmation_gate_agent_hifo_v1.json` | R10 |
| 13 | `bp_confirmation_gate_only_proxy_diagnostic_v1.json` | R10 |
| 14 | `bp_confirmation_gate_only_proxy_v1.json` | R10 |
| 15 | `bp_cross_distribution_confirmation_proxy_v1.json` | R10 |
| 16 | `bp_cross_distribution_local_refine_proxy_v1.json` | R10 |
| 17 | `bp_dual_agent_generalization_confirm_v1.json` | R10 |
| 18 | `bp_falsifiable_mechanism_ecology_creation_pilot_v1.json` | R19 |
| 19 | `bp_fme_action_order_v2_proposal.json` | R19 |
| 20 | `bp_m3_confirm.json` | R04 |
| 21 | `bp_m3_pilot.json` | R04 |
| 22 | `bp_numeric_neighborhood_proxy_v1.json` | R11 |
| 23 | `bp_numeric_pair_compensation_proxy_v1.json` | R11 |
| 24 | `bp_objective_feedback_confirm_v1.json` | R09 |
| 25 | `bp_objective_feedback_proxy_v1.json` | R09 |
| 26 | `bp_q3_fused_confirmation_v1.json` | R07 |
| 27 | `bp_q3_mechanism_discovery_v1.json` | R07 |
| 28 | `bp_robust_feedback_proxy_diagnostic_v1.json` | R09 |
| 29 | `bp_robust_feedback_proxy_v1.json` | R09 |
| 30 | `bp_scale_balanced_feedback_proxy_v1.json` | R09 |
| 31 | `bp_scale_proxy_diagnostic_v1.json` | R09 |
| 32 | `bp_scale_structured_feedback_proxy_v1.json` | R09 |
| 33 | `bp_scale_structured_proxy_diagnostic_v1.json` | R09 |
| 34 | `core_benchmark_registry.json` | R28 |
| 35 | `cross_problem_transfer_v1.json` | R08 |
| 36 | `cvrp_confirmation_portability_proxy_v1.json` | R15 |
| 37 | `cvrp_core_final_report_v1.json` | R15 |
| 38 | `cvrp_environment_gate_audit_v1.json` | R15 |
| 39 | `cvrp_expert_router_proxy_deepseek_fallback_v1.json` | R17 |
| 40 | `cvrp_expert_router_proxy_v1.json` | R17 |
| 41 | `cvrp_fresh_generated_diagnostic_v1.json` | R15 |
| 42 | `cvrp_multi_environment_e1e2_proxy_v1.json` | R15 |
| 43 | `cvrp_multi_environment_e1e2_retry_v1.json` | R15 |
| 44 | `cvrp_multi_environment_feedback_proxy_v1.json` | R15 |
| 45 | `cvrp_multi_environment_fresh_diagnostic_v1.json` | R15 |
| 46 | `cvrp_pairwise_abstain_backup_dev_v1.json` | R16 |
| 47 | `cvrp_pairwise_selector_ablation_dev_v1.json` | R16 |
| 48 | `cvrp_router_reevo_inspired_v2.json` | R17 |
| 49 | `cvrp_structural_memory_proxy_v1.json` | R15 |
| 50 | `cvrp_structure_fresh_diagnostic_v1.json` | R15 |
| 51 | `data_collection_bp_online.json` | R03 |
| 52 | `data_collection_cvrp.json` | R03 |
| 53 | `data_collection_tsp.json` | R03 |
| 54 | `gen16_bp_online.json` | R05 |
| 55 | `gen16_cvrp_construct.json` | R05 |
| 56 | `gen16_tsp_construct.json` | R05 |
| 57 | `high_gen_bp_online.json` | R05 |
| 58 | `high_gen_cvrp_construct.json` | R05 |
| 59 | `high_gen_tsp_construct.json` | R05 |
| 60 | `inherited_pool_control_v1.json` | R05 |
| 61 | `m3_operator_screen_v1.json` | R04 |
| 62 | `m3_tsp_confirmation_v1.json` | R04 |
| 63 | `phase4b_bp_online_ADE2.json` | R04 |
| 64 | `phase4b_bp_online_E2_seeded.json` | R04 |
| 65 | `phase4b_explore_tsp_F1.json` | R04 |
| 66 | `phase4b_explore_tsp_F2.json` | R04 |
| 67 | `phase4b_explore_tsp_F3.json` | R04 |
| 68 | `phase4b_explore_tsp.json` | R04 |
| 69 | `phase4b_llm_rerank_cvrp.json` | R04 |
| 70 | `phase4b_llm_rerank_tsp.json` | R04 |
| 71 | `rag_ablation_4arm_cvrp.json` | R03 |
| 72 | `rag_ablation_4arm_tsp.json` | R03 |
| 73 | `rag_ablation_r2_tsp_D_continue.json` | R03 |
| 74 | `rag_ablation_r2_tsp_D_only.json` | R03 |
| 75 | `rag_ablation_r2_tsp_D_r4r5.json` | R03 |
| 76 | `rag_ablation_smoke_cvrp.json` | R03 |
| 77 | `refactor0830_online_pilot_v2.json` | R24 |
| 78 | `refactor0830_opencode_go_pilot_v4.json` | R24 |
| 79 | `refactor0830_opencode_go_pilot_v5.json` | R24 |
| 80 | `refactor0830_opencode_go_pilot_v6.json` | R24 |
| 81 | `refactor0830_opencode_go_pilot_v7.json` | R24 |
| 82 | `refactor0830_opencode_pilot_v3.json` | R24 |
| 83 | `refactor0830_rq1_rq4_offline_replay_v1.json` | R23 |
| 84 | `refactor0830_rq1b_v1.json` | R25 |
| 85 | `refactor0830_rq1b_v2.json` | R25 |
| 86 | `tsp_search_controller_agent_memory_proxy_v1.json` | R12 |
| 87 | `tsp_search_controller_feedback_rag_proxy_v1.json` | R12 |
| 88 | `tsp_search_controller_objective_feedback_proxy_v1.json` | R12 |
| 89 | `tsp_search_controller_proxy_v1.json` | R12 |
| 90 | `tsp_search_controller_proxy_v2.json` | R12 |
| 91 | `tsp_search_controller_seed_diversity_confirm_v1.json` | R12 |
| 92 | `tsp_search_controller_seed_diversity_proxy_v1.json` | R12 |
| 93 | `warm_fixed_gen40_bp.json` | R04 |

## 5. A–CE 历史探索的逐阶段账本

当前树中可按阶段标签定位到 58 个阶段。以下均为历史局部结论，没有本次重算；来源链接指向代表性结果，完整同阶段文件由CSV索引补齐。相邻阶段仍分行，避免把失败支线埋在最终TSP管线后。

| 阶段 | 研究内容与结论边界 | 证据 |
|---|---|---|
| A | 605精英AST结构审计，迁移先验不等于收益。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5A-605%E7%B2%BE%E8%8B%B1%E4%BB%A3%E7%A0%81%E7%BB%93%E6%9E%84%E7%9B%B8%E4%BC%BC%E5%BA%A6_2026-07-14_000239.json) |
| C | Q3机制发现；不能从answer方向性优势推出严格双卡协同。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5C-Q3%E6%9C%BA%E5%88%B6%E5%8F%91%E7%8E%B0_2026-07-14_0136/mechanism_summary.json) |
| D | 融合语义独立确认未稳定复现。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5D-%E8%9E%8D%E5%90%88%E8%AF%AD%E4%B9%89%E7%8B%AC%E7%AB%8B%E7%A1%AE%E8%AE%A4_2026-07-14_0236/confirmation_summary.json) |
| E | m3三问题初筛，浅预算亮点不能直接晋升。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5E-m3%E4%B8%89%E9%97%AE%E9%A2%98%E9%85%8D%E5%AF%B9%E7%AD%9B%E6%9F%A5_2026-07-14_0307/m3_summary.json) |
| F | TSP m3深预算未确认，历史主线排除m3。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5F-TSP-m3%E6%B7%B1%E9%A2%84%E7%AE%97%E7%A1%AE%E8%AE%A4_2026-07-14_0336/m3_tsp_summary.json) |
| H | 历史top6短预算热启动有积极观察，成本和大规模有效性成为风险。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5H-%E5%8E%86%E5%8F%B2top6%E7%83%AD%E5%90%AF%E5%8A%A8%E5%AF%B9%E7%85%A7_2026-07-14_0406/inheritance_summary.json) |
| AE | 运行探针跨seed验证。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5AE-%E8%BF%90%E8%A1%8C%E6%8E%A2%E9%92%88%E8%B7%A8seed%E9%AA%8C%E8%AF%81_2026-07-14_0540/validation_summary.json) |
| AF | 合成n442负类验证，检查失败候选辨识。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5AF-%E5%90%88%E6%88%90442%E8%B4%9F%E7%B1%BB%E9%AA%8C%E8%AF%81_2026-07-14_0552/validation_442_summary.json) |
| AG | probe选择反事实，分离选择与候选贡献。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5AG-probe%E9%80%89%E6%8B%A9%E5%8F%8D%E4%BA%8B%E5%AE%9E_2026-07-14_0600/probe_selection_counterfactual_summary.json) |
| AI | fresh对称探针；主要留下manifest，不补写结果。 | manifest为主；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5AI-fresh%E5%AF%B9%E7%A7%B0%E8%BF%90%E8%A1%8C%E6%8E%A2%E9%92%88_2026-07-14_0606/fresh_probe_manifest.json) |
| AJ | Core12扩展，保留失败/超时。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5AJ-Core12%E6%89%A9%E5%B1%95%E8%AF%84%E4%BC%B0_2026-07-14_0610/full12_summary.json) |
| AK | 合成探针到pcb442迁移。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5AK-%E5%90%88%E6%88%90%E6%8E%A2%E9%92%88%E5%88%B0pcb442%E8%BF%81%E7%A7%BB_2026-07-14_0650/probe_transfer_summary.json) |
| AL | n442目标感知选择后在Core12验证。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5AL-n442%E9%80%89%E6%8B%A9Core12%E8%AF%84%E4%BC%B0_2026-07-14_0700/target_aware_core12_summary.json) |
| AM | 只读安全档案反事实。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5AM-%E5%8F%AA%E8%AF%BB%E5%AE%89%E5%85%A8%E6%A1%A3%E6%A1%88%E5%8F%8D%E4%BA%8B%E5%AE%9E_2026-07-14_0710/safety_archive_summary.json) |
| AN | 安全档案pcb3038探针，检查规模外推。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5AN-%E5%88%9D%E5%A7%8B%E5%AE%89%E5%85%A8%E6%A1%A3%E6%A1%88pcb3038%E6%8E%A2%E9%92%88_2026-07-14_0720/validation_summary.json) |
| AO | 评估器成本基线，超时含评测器自身成本。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5AO-pcb3038%E8%AF%84%E4%BC%B0%E5%99%A8%E6%88%90%E6%9C%AC%E5%9F%BA%E7%BA%BF_2026-07-14_0730/evaluator_floor_summary.json) |
| AP | 影子评估器验证，分离执行基础设施问题。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5AP-TSP%E5%BD%B1%E5%AD%90%E8%AF%84%E4%BC%B0%E5%99%A8%E9%AA%8C%E8%AF%81_2026-07-14_0740/shadow_evaluator_summary.json) |
| AQ | 修复后重算Core12，版本边界独立。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5AQ-%E4%BF%AE%E5%A4%8D%E5%90%8ECore12%E9%87%8D%E7%AE%97_2026-07-14_0800/fixed_core12_summary.json) |
| AR | 失败坐标串行复核，并发成本不是算法质量。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5AR-Core12%E5%A4%B1%E8%B4%A5%E5%9D%90%E6%A0%87%E4%B8%B2%E8%A1%8C%E5%A4%8D%E6%A0%B8_2026-07-14_0810/fixed_core12_summary.json) |
| AS | 质量/规模双档案，分开表达目标。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5AS-%E5%8E%86%E5%8F%B2%E6%B1%A0%E8%B4%A8%E9%87%8F%E8%A7%84%E6%A8%A1%E5%8F%8C%E6%A1%A3%E6%A1%88_2026-07-14_0749/audit_summary.json) |
| AT | 质量档案Core12；质量排序不保证安全运行。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5AT-%E8%B4%A8%E9%87%8F%E6%A1%A3%E6%A1%88Core12_2026-07-14_1005/archive_core12_summary.json) |
| AU | 小规模非泄漏探针false-safe较高，不能直接外推。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5AU-%E5%85%A8%E5%8E%86%E5%8F%B2%E6%B1%A0%E9%9D%9E%E6%B3%84%E6%BC%8F%E8%BF%90%E8%A1%8C%E6%8E%A2%E9%92%88_2026-07-14_1034/runtime_probe_summary.json) |
| AV | 级联合成探针：排序信号不等于时间校准。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5AV-%E5%A4%A7%E8%A7%84%E6%A8%A1%E5%90%88%E6%88%90dev%E7%BA%A7%E8%81%94%E6%8E%A2%E9%92%88_2026-07-14_1105/runtime_probe_summary.json) |
| AW | 目标规模直接探针在该面板0 false-safe，范围仅此面板。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5AW-%E7%9B%AE%E6%A0%87%E8%A7%84%E6%A8%A1%E5%90%88%E6%88%90dev%E7%9B%B4%E6%8E%A5%E6%8E%A2%E9%92%88_2026-07-14_1134/direct_scale_probe_summary.json) |
| AX | 新目标规模合成确认，不等于TSPLIB泛化。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5AX-%E5%85%A8%E6%96%B0%E5%90%88%E6%88%90%E7%9B%AE%E6%A0%87%E8%A7%84%E6%A8%A1%E6%A1%A3%E6%A1%88%E7%A1%AE%E8%AE%A4_2026-07-14_1235/scale_archive_confirmation_summary.json) |
| AY | 安全过滤后的质量/速度前沿重排。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5AY-%E5%AE%89%E5%85%A8%E6%B1%A0%E8%B4%A8%E9%87%8F%E9%80%9F%E5%BA%A6%E5%89%8D%E6%B2%BF_2026-07-14_1245/safe_pool_frontier_summary.json) |
| AZ | 质量速度前沿独立合成确认。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5AZ-%E8%B4%A8%E9%87%8F%E9%80%9F%E5%BA%A6%E5%89%8D%E6%B2%BF%E7%8B%AC%E7%AB%8B%E7%A1%AE%E8%AE%A4_2026-07-14_1332/frontier_archive_confirmation_summary.json) |
| BA | 15个非空子集压缩发现；单槽看似最好，缺独立JSON。 | 图中历史摘要；[来源](../../docs/diagrams/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BA-%E6%9C%80%E5%B0%8F%E5%85%85%E5%88%86%E6%A1%A3%E6%A1%88%E5%88%86%E6%9E%90_2026-07-14_1345/%E9%98%B6%E6%AE%B5BA-%E5%9B%9B%E6%A7%BD%E5%8E%8B%E7%BC%A9%E4%B8%BA%E5%8D%95%E6%A7%BD%E7%9A%84%E8%AF%81%E6%8D%AE%E9%93%BE.drawio) |
| BB | R4单槽新三例1胜2负，覆盖不足。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BB-%E5%8D%95%E6%A7%BD%E5%BF%AB%E9%80%9F%E6%A1%A3%E6%A1%88%E7%8B%AC%E7%AB%8B%E7%A1%AE%E8%AE%A4_2026-07-14_1341/frontier_archive_confirmation_summary.json) |
| BC | R2+R4双槽合成确认通过。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BC-%E5%BF%AB%E9%80%9F%E5%8F%8C%E6%A7%BD%E6%A1%A3%E6%A1%88%E7%8B%AC%E7%AB%8B%E7%A1%AE%E8%AE%A4_2026-07-14_1344/frontier_archive_confirmation_summary.json) |
| BD | 双槽真实Core12为3胜9负，不替代四槽。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BD-%E5%BF%AB%E9%80%9F%E5%8F%8C%E6%A7%BD%E6%A1%A3%E6%A1%88Core12%E5%A4%96%E9%83%A8%E9%AA%8C%E8%AF%81_2026-07-14_1401/archive_core12_summary.json) |
| BE | 合成到真实实例排名反转，仅图摘要。 | 图中历史摘要；[来源](../../docs/diagrams/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BE-%E5%90%88%E6%88%90%E7%9C%9F%E5%AE%9E%E6%8E%92%E5%90%8D%E6%BC%82%E7%A7%BB_2026-07-14_1418/%E9%98%B6%E6%AE%B5BE-%E4%BB%A3%E7%A0%81%E6%8E%92%E5%90%8D%E5%8F%8D%E8%BD%AC.drawio) |
| BF | 简单几何特征未解释迁移差异，仅图摘要。 | 图中历史摘要；[来源](../../docs/diagrams/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BF-%E5%AE%9E%E4%BE%8B%E5%87%A0%E4%BD%95%E7%89%B9%E5%BE%81%E6%8E%A2%E7%B4%A2_2026-07-14_1428/%E9%98%B6%E6%AE%B5BF-%E7%AE%80%E5%8D%95%E5%87%A0%E4%BD%95%E7%89%B9%E5%BE%81%E6%9C%AA%E8%A7%A3%E9%87%8A%E8%BF%81%E7%A7%BB%E5%B7%AE%E5%BC%82.drawio) |
| BG | 路线行为相关信号，不是因果。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BG-%E8%B7%AF%E7%BA%BF%E8%A1%8C%E4%B8%BA%E7%AD%BE%E5%90%8D_2026-07-14_1438/route_behavior_summary.json) |
| BH | 外部56例33胜23负，未证明普遍替代四槽。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BH-%E5%A4%96%E9%83%A8TSPLIB%E7%9C%9F%E5%AE%9E%E7%A1%AE%E8%AE%A4_2026-07-14_1500/external_confirmation_summary.json) |
| BI | 140个运行前selector阈值无一过门，停止分支。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BI-%E5%BF%AB%E9%80%9F%E5%8F%8C%E6%A7%BD%E9%80%89%E6%8B%A9%E5%99%A8_2026-07-14_1435/fit_summary.json) |
| BJ | 降低边长波动多数更差，不作为优化目标。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BJ-%E8%BE%B9%E9%95%BF%E6%B3%A2%E5%8A%A8%E5%9B%A0%E6%9E%9C%E5%B9%B2%E9%A2%84_2026-07-14_1443/intervention_summary.json) |
| BK | 匹配修复只解释约15.1%差距。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BK-%E5%8F%8C%E6%A1%A3%E6%A1%88%E5%8C%B9%E9%85%8D%E5%B1%80%E9%83%A8%E4%BF%AE%E5%A4%8D_2026-07-14_1457/matched_repair_summary.json) |
| BL | 源码槽不等于功能槽；AW1/AW3重复，R2/R4互补。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BL-%E5%8A%9F%E8%83%BD%E8%B7%AF%E7%BA%BF%E5%A4%9A%E6%A0%B7%E6%80%A7_2026-07-14_1508/functional_diversity_summary.json) |
| BM | 三槽在3个高规模实例覆盖full oracle，样本不足。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BM-%E9%AB%98%E8%A7%84%E6%A8%A1%E5%A4%9A%E6%A0%B7%E4%B8%89%E6%A7%BD%E7%A1%AE%E8%AE%A4_2026-07-14_1524/high_scale_summary.json) |
| BN | 四种AW源码主体代数等价，hash/AST不能证明功能多样。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BN-AW%E6%BA%90%E7%A0%81%E8%AF%AD%E4%B9%89%E5%86%97%E4%BD%99_2026-07-14_1545/source_semantic_audit.json) |
| BO | 廉价功能探针在冻结面板precision/recall为1，非普适保证。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BO-%E5%BB%89%E4%BB%B7%E5%8A%9F%E8%83%BD%E6%8E%A2%E9%92%88%E9%AA%8C%E8%AF%81_2026-07-14_1550/frozen_probe_summary.json) |
| BP | 99条安全代码归为50功能簇，未删除历史池。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BP-%E5%8E%86%E5%8F%B2%E5%AE%89%E5%85%A8%E6%B1%A0%E5%8A%9F%E8%83%BD%E5%86%97%E4%BD%99_2026-07-14_1615/safe_pool_functional_redundancy_summary.json) |
| BQ | 12-code组合外部28例25胜3平，均值改善约3.82%。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BQ-%E5%85%A8%E5%8E%86%E5%8F%B2%E6%B1%A0%E8%B4%A8%E9%87%8F%E7%BB%84%E5%90%88_2026-07-14_1655/confirmation_summary.json) |
| BR | 高规模3例继续改善；固定5步随机修复几乎无收益。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BR-%E9%AB%98%E8%A7%84%E6%A8%A1%E8%B4%A8%E9%87%8F%E7%BB%84%E5%90%88%E4%B8%8E%E5%9B%BA%E5%AE%9A%E4%BF%AE%E5%A4%8D_2026-07-14_1745/high_scale_quality_summary.json) |
| BS | 近邻2-opt是主要附加收益，归于固定优化器。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BS-%E8%BF%91%E9%82%BB%E5%BC%95%E5%AF%BC%E5%B1%80%E9%83%A8%E6%90%9C%E7%B4%A2_2026-07-14_1815/confirmation_nearest_two_opt_summary.json) |
| BT | 提前停止延长到自然收敛带来收益，预算变化单列。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BT-%E7%A1%AE%E5%AE%9A%E6%80%A7%E8%BF%AD%E4%BB%A3%E5%B1%80%E9%83%A8%E6%90%9C%E7%B4%A2_2026-07-14_1830/iterated_nearest_two_opt_summary.json) |
| BU | 单节点移位继续带来收益。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BU-%E5%8D%95%E8%8A%82%E7%82%B9%E7%A7%BB%E4%BD%8D%E5%8F%98%E9%82%BB%E5%9F%9F_2026-07-14_1850/relocation_vnd_summary.json) |
| BV | 增加移位预算收益未过门，停止堆预算。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BV-%E5%8D%95%E8%8A%82%E7%82%B9%E7%A7%BB%E4%BD%8D%E6%94%B6%E6%95%9B%E8%BE%B9%E7%95%8C_2026-07-14_1910/relocation_vnd_summary.json) |
| BW | Or-opt-2开发集小幅收益。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BW-%E8%BF%9E%E7%BB%AD%E4%B8%A4%E8%8A%82%E7%82%B9%E7%A7%BB%E4%BD%8D_2026-07-14_1930/or_opt_2_vnd_summary.json) |
| BX | Or-opt-2外部总体门槛失败。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BX-Or-opt-2%E5%A4%96%E9%83%A8%E7%A1%AE%E8%AE%A4_2026-07-14_1950/external_or_opt_2_summary.json) |
| BY | Or-opt-2大实例方向复现但幅度不足。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BY-%E5%A4%A7%E5%AE%9E%E4%BE%8BOr-opt-2%E4%BA%A4%E5%8F%89%E7%A1%AE%E8%AE%A4_2026-07-14_2015/external_or_opt_2_summary.json) |
| BZ | Or-opt-3开发集有效。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5BZ-%E8%BF%9E%E7%BB%AD%E4%B8%89%E8%8A%82%E7%82%B9%E7%A7%BB%E4%BD%8D_2026-07-14_2035/or_opt_3_summary.json) |
| CA | Or-opt-3外部近乎无收益，停止扩展片段长度。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5CA-Or-opt-3%E5%A4%96%E9%83%A8%E7%A1%AE%E8%AE%A4_2026-07-14_2055/external_or_opt_3_summary.json) |
| CB | 8次盆地重启收益不足，不默认化。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5CB-%E5%85%A8%E9%82%BB%E5%9F%9F%E7%9B%86%E5%9C%B0%E9%87%8D%E5%90%AF_2026-07-14_2115/full_vnd_restart_summary.json) |
| CC | 受限三边重连开发集改善。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5CC-%E5%8F%97%E9%99%90%E4%B8%89%E8%BE%B9%E9%87%8D%E8%BF%9E_2026-07-14_2210/restricted_three_opt_summary.json) |
| CD | 受限3-opt在28例外部确认通过。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5CD-%E5%8F%97%E9%99%90%E4%B8%89%E8%BE%B9%E9%87%8D%E8%BF%9E%E5%A4%96%E9%83%A8%E7%A1%AE%E8%AE%A4_2026-07-14_2245/external_restricted_three_opt_summary.json) |
| CE | 高规模自然收敛有增益，仅3个开发实例。 | 结构化摘要/协议；[来源](../../agent_records/archive/obsidian_20260718/%E8%87%AA%E4%B8%BB%E7%A7%91%E7%A0%94%E5%BE%AA%E7%8E%AF_2026-07-13_235608/%E7%BB%93%E6%9E%9C/%E9%98%B6%E6%AE%B5CE-%E9%AB%98%E8%A7%84%E6%A8%A1%E4%B8%89%E8%BE%B9%E9%87%8D%E8%BF%9E%E6%94%B6%E6%95%9B%E8%BE%B9%E7%95%8C_2026-07-14_2305/restricted_three_opt_summary.json) |

当前按文件阶段标签未找到 B、G、I–AD、AH 的独立阶段产物。字母不连续是归档事实，不据此编造实验；例如 BA/BE/BF 仅有图中摘要，AI主要有manifest。D0–D32使用另一套阶段命名，与这里的D不是同一条路线。

历史阶段结论中 TSP 的“当前主线”指当时的研究时间点。最终推荐新首版使用 CVRP 的理由是：当前FME已有轻量合成CVRP评测接口、最新分支已集中于CVRP，且可以不依赖TSP大型portfolio和局部搜索预算。该选择是按当前工程目标做的设计判断，不是断言CVRP科学潜力一定高于TSP。

## 6. FME恢复与未实施分支的完整性补充

| 范围 | 保留事实 | 不应误读为 |
|---|---|---|
| order-regime前期 | 同multiset换顺序、两个候选的有界开发诊断、descriptor与反馈接口 | 全问题统一诊断或自动机制发现 |
| ORF-001..005 | candidate/checkpoint/behavior/evaluator/feedback身份绑定、完整摘要、缓存归属、失败hash、平局准入修订 | 在新runner中已自动接通 |
| D0 | 证据身份、初始population投影、verifier绑定 | 当前机器已跑过全部历史验证 |
| D1 | 历史action receipt→counterexample→claim弱化→repair链；恢复时标为静态集成未验证 | 已经证明质量提高 |
| D2 | 遮蔽反例/弱化证据使repair/m1变成invent/e1；6候选仍同一内在行为单元 | 动作变化等于有用新算法 |
| D3–D7 | 档案几何有支持，parent exposure、regularization、useful novelty没有支持 | 可以启用behavior_cover |
| D8–D32 | 单决策正向见证未组成端到端合法的全局/无状态稀疏策略 | 局部反例能直接拼成可部署skill |
| 被排除资产 | behavior_cover、decision_trace、p5_controller_adapter、一次性实验、旧粗行为单元改写、D21–25激活等不在精选恢复范围 | 本次漏检或应该恢复的主线依赖 |
| Phase1–3 | 组合根、真实三问题适配、分析与档案、历史检索/指标的实现与静态/既往验收记录 | 所有研究假设已成立 |
| Phase4–5 | 历史replay、新在线pilot、精简报告/审计；之后RQ1b另有明确合同 | 可以跨cohort混合所有数字 |
| Phase6 | JSSP优先的单领域generalization提案；MaxCut/Knapsack合同也存在 | 三个新问题已可执行 |

D0–D32只有精选回流记录和来源hash，不具备逐个原始实验的完整本地包。报告因此按有证据的范围分组，并保留源记录指出的缺失；不把D8–D32拆成25个没有证据的“详细成果”。

## 7. 支线负结果与未完成状态的处理

Go框架静态RAG报告在26个配对格记录0胜、18负、8平，相比无RAG不占优；该协议reps=1且将5张卡全部塞入，不能外推为所有检索方法无效。参考 `evidence/go_eoh_rag_20260705/framework_rag_vs_norag_report.md`。少量卡/reranker当时只是待测假设。

对文献型handoff（EoH、ReEvo、EoHS、AutoFolio、TTP算法选择、HYDRA、SATzilla等），本目录将其关联到R02/R16/R17，不将“读过一篇论文”另计为实现了一条科研路线。本轮没有重复搜索这些旁支文献。对provider恢复、输出修复和审计，分别计入R24/R25/R28工程支撑，保留中断/未批准/未启动状态，不当成新的算法成果。
