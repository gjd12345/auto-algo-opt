# 科研主线

本文是 Refactor0830 上「有哪些路线、哪一条还在做」的指针。
它不改写任何冻结报告，也不授权新实验。

**活的主线只有一句：**
在同一个 `FMEResearchLoop` 里，评测前的代码行为预测，能不能在同预算下改善 CVRP 构造启发式的搜索。

当前实验形态是 RQ1b：CVRP × DeepSeek V4 Flash × 三臂（标量 / 普通被动 / 行为约束被动）。
完整性已通过，科研继续门槛未通过。没有新的 `--execute` 授权。

---

## 1. 为什么必须收敛

仓库里叠了三套「当前正式」叙事，不能同时当真：

| 叙事 | 来源 | 实际身份 |
|---|---|---|
| 反馈-RAG Agent，EOH 仍是进化引擎 | `baseline_contract.json` 仍标 `active` | 2026-07-14 旧基线 |
| FME 闭环，门在 P0 / D0 | `baseline_contract_v2`、depth-first 修正 | 2026-07-24/30 架构，已被 RQ1b 收窄 |
| RQ1b 行为分析，等新授权 | README、`research_state.json`、RQ1b 契约 | **现在以这套为准** |

另外，`agent_records/inventories/research_assets_v1.md` 仍把 `tsp_search_controller`、`cvrp_expert_router` 算进「当前正式问题」。
那是 2026-07-19 的冻结清单，代码注册表已经只剩三个构造问题。

读本文件时：以 README + `research_state.json` + 本文为准；旧契约只当历史。

---

## 2. 活主线：RQ1b

**问题。** 给定代码和合法前缀上的干预状态，模型能不能预测 `select_next_node` 的返回值，并把这种预测回流到同预算搜索里。

**设计约束。**

- 唯一控制器仍是 `FMEResearchLoop`，三臂都锁成固定发明节奏，没有主动反例、修复或迁移。
- A 臂做影子预测但不回流；B/C 回流评测前预测；实测标签永不回流。
- 全部 incumbent 冻结后才打开 held-out。
- 行为题借鉴 CRUXEval-O 的「给代码和输入，预测输出」，但状态是自造干预，不是那份数据。

**已完成队列（同一 v2 协议，不是新 cohort）。**

- 24 单元 × 16 槽 = 384 次尝试；36 条同代码诊断；24 个 held-out
- Integrity 通过；Behavior / Target / Search / Chain 未过
- 同代码行为准确率 C−B = −0.93 个百分点（B 48.15%，C 47.22%）
- Potential-AUC 中位 +1.24 个百分点，但不能归因于「更懂行为」
- 有效候选率 87.50% → 82.03%，超过允许的 5 个百分点

**下一问（若再授权，必须新协议、新目录）。**
为什么行为准确率没升、有效率下降。不是再堆 seed，也不是打开 RQ2–RQ4。

---

## 3. 冻结支柱（可写进论文，不可与 RQ1b 混算）

这两条已经结束，用来证明「搜索底盘能出算法」，不是当前探索议程。

1. **岛屿模型 605 次运行**（`evidence/final_batch_20260630/`）  
   BP 最优 0.00674（+83.1%），TSP 6.004（+8.5%），CVRP 12.356（+8.6%）。  
   实例协议与 FME 合成实例不同。

2. **Q3 策略卡**（`reports/strategy_experiments/q3_v2/`）  
   answer 相对 pure：10 个完整配对，7/0/3，中位增益 0.7275，判定 `directional_support`。  
   组件实验支持双卡互补或上下文交互，不宣称加性。  
   跨问题迁移 `inconclusive`（TSP 0/5 完整配对）。

BP 最优式的可解释性（同尺寸预留）是 605 的附录，见 `evidence/bp_interpretability/`。

---

## 4. 全路线清单

状态含义：`活` = 当前唯一科学问题；`冻结` = 有完整证据、可引用但不再扩面；`暂停` = 契约还在、禁止当新主线；`失败/未完成` = 队列不完整，禁止并表；`否决` = 明确不要当贡献；`仅契约` = 没跑过。

### A. FME / 科研 Agent

| 路线 | 状态 | 一句话 |
|---|---|---|
| RQ1b v2 续跑 | **活 / 完整性通过、科学门槛未过** | 见第 2 节 |
| RQ1b v1 | 失败/未完成 | 14/4/6 单元；禁止并入 v2 |
| RQ1b v2 中断前缀 | 失败/未完成 | 同一协议的前缀，不是新队列 |
| RQ1b 夹具 | 冻结（非科学） | 只证明执行链 |
| RQ1–RQ4 在线 v7 | 冻结探索 / RQ2–RQ4 暂停 | 81/81 完整；主动、历史、抽象提示、Pro 均无稳定额外收益 |
| 在线 v2–v6 | 失败/未完成 | Model Router 403、Zen 401、超时、断连；v6 禁止并入 v7 |
| 离线 RQ 回放 | 冻结包装 | 用历史表回答契约 RQ，不是新效应 |
| BP FME 创建试点 v1 | 冻结：mechanism_only | 质量门失败；e2+m2 占 48/60 槽 |
| BP FME action-order v2 | 仅契约 | 从未启动 |
| 基线契约 RQ1–RQ4 | 暂停（论题仍在） | 与 v7 的 9 臂矩阵不是同一套操作定义 |
| D0–D1 深度优先 | 暂停 / 零 API | 反例必须改变下一生成动作；本工作区未重放 |
| D2–D32、behavior_cover | 否决 | 动作路径变化 ≠ 质量；局部干预不能合成全局策略 |
| `legacy_stacked` 宽度控制 | 否决（新主张） | 只允许历史回放 |
| Phase 6 JSSP / MaxCut / Knapsack | 暂停 / 仅契约 | 无评测器、无划分哈希 |
| 顺序体制 ORF | 暂停，默认关闭 | 可作 BP 诊断附录，不是第二控制器 |
| 基线 P0 ORF-001–005 | 未关闭 | 挡住 ORF 接入，不是结果 |
| 基线 F1–F4 | 仅契约 | 元提示 / 稀疏评测 / 树生成 / 快慢路由；v7 未授权 |

### B. 官方 EOH + RAG + 策略卡（Python 构造问题）

| 路线 | 状态 | 一句话 |
|---|---|---|
| 岛屿 605 | 冻结支柱 | 见第 3 节 |
| high_gen / gen16 | 并入 605 | 不是独立主张 |
| BP 同尺寸预留 | 冻结附录 | 回放 0.006741；TRD 里的公式消融未落地 |
| RAG 四臂 | 冻结 | CVRP C 相对 A 中位约 −5.95%；TSP 无支持；D 臂种群特征未加载 |
| RAG R2 TSP D | 探索 | 最好一次 6.110，不是锁定中位协议 |
| Phase 4b LLM 重排 | 冻结 | TSP E2 最好但仍 <5%；E1 模式坍缩 |
| Phase 4b BP E2 播种 | 探索 | 最好一次 0.0249；冷启动自适应未找回 0.00674 |
| Phase 4b TSP F1–F3 | 设计无报告 | 仓库里没有结果文 |
| 自适应 / 暖启动 gen40 | 冻结过程 | 暖启动是复制精英，不是新发现 |
| 数据收集 / rerank SFT | 工程 | 蒸馏未上线推理 |
| TOCC 卡片 | 复现-only | CVRP 约 4%；TSP 噪声大；不是控制器 |
| 卡片合成 / 词表隔离 | 基础设施 | 历史 EOH 副作用路径 |
| Q3 v2 | 冻结支柱 | 见第 3 节 |
| Q3 组件 | 冻结 | 双卡互补或上下文交互 |
| Q3 机制发现 | 否定 | `no_clear_mechanism` |
| Q3 融合语义确认 | 否定 | `not_confirmed` |
| 跨问题抽象卡 | 未决 | TSP 0/5 配对 |
| 对抗失败模式 | 缺口 | 缺 `failures_*.jsonl` |
| 继承池对照 | 候选 | TSP held-out 3/3，未当质量门 |
| m3 算子 | 否决 | TSP 确认失败，不进共享进化 |
| 目标感知 / 数值邻域 / 稳健反馈 / 尺度代理 | 过程诊断 | 多份 `bp_*_proxy`；若干 discovery 资产标明不可作正式种子 |

### C. 换了被进化对象，或换了语言

| 路线 | 状态 | 一句话 |
|---|---|---|
| TSP search-controller | 复现-only | 进化的是 `build_search_plan`，不是 `select_next_node` |
| TSP 局部搜索教师库 | 过程 | 2-opt / relocate / or-opt / 3-opt 安全池；服务上一条 |
| CVRP expert-router | 否决 | 代理门失败：从未用到两个专家 |
| 成对代价选择器 | 否决 | `do_not_promote` |
| Hydra 组合反馈 | 未激活 | 实现了，没进正式 manifest |
| Go InsertShips / 背包 / 混载 | 复现-only | 另一套语言和评测器 |
| SmartOperator | 复现-only | Go 上的第二进化环 |
| Go EOH-RAG | 否定 | 框架 5 卡 RAG 有害（0/18/8） |

---

## 5. 证据分层（禁止并表）

1. 岛屿 605 / Q3：官方 EOH 实例与 gap。
2. FME 在线 v7 / RQ1b：独立合成实例；箱数、路线长度不可和 1 混算。
3. v1、未完成 v2、v6：不完整队列。
4. Go、search-controller、router：不同对象或不同语言。

`mix_cohorts: false`。Flash/Pro 只允许出现在预注册的 RQ4 臂，且 RQ4 已暂停。

---

## 6. 默认命令

```bash
# 只冻结
python -m eoh_rag.fme.rq1b_v2 --output outputs/fme_pilot/rq1b_prepared_new

# 只读审计（需要本机 outputs）
python scripts/audit_rq1b_resume.py \
  outputs/fme_pilot/rq1b_online_20260831_v2_resume_v1 \
  --output outputs/rq1b_resume_audit_recheck.json
```

没有新授权不要 `--execute`，不要往旧 `outputs/fme_pilot/` 续写。

---

## 7. 若目标是写论文而不是再跑

主表用岛屿 605 与 Q3 方向性支持。  
系统部分写 FME 作为「每 tick 一个可回放动作」的控制面。  
RQ1b 写成开放问题：执行完整，行为预测没有立住，主动反例没有稳定额外收益。  
不要把 v7 的九臂探索写成已经证实的机制生态。
