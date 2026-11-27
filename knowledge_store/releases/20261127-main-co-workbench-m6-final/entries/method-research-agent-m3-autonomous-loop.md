# 无人值守组合优化自主研究代理与持久预算状态机 (M3 ResearchAgent · research_agent)

本条目记录里程碑三建成的独立多轮自主研究代理系统（`research_agent/`），核心目标是在**严格单进程/跨进程共享总请求硬上限 `B_total=36`**与**物理拆离 `dev_24 / select_64 / blind_120`**下，仅凭工具观察与自我反思自主完成组合优化算法设计与验证。

## 定义或方法步骤

1. **双层持久请求账本 (`PersistentRequestBudget`)**：以 SQLite WAL 实现 `reserved -> sent -> complete/failed/unknown` 原子状态机，外层 Reason–Act–Reflect 与内层 Session EoH 共享同一余额与 `response_sha256` 审计轨迹，支持断点零重复恢复。
2. **结构化工具链与防幻觉约束**：集成 7 类工具（`kb_search/kb_read`、`diagnose_suite` 五因子切片、`run_math_sandbox` AST 只读沙箱、`list_interfaces` + `propose_and_validate_interface` 五关预检、`submit_plan_and_evolve`、`archive_query` 踏脚石档案、带证据 SHA-256 强制核验的 `hypotheses.jsonl` 账本与 AST 查重防退化守卫）。
3. **双预算 3 种子闭环稳定性**：`standard_500ms`（12 场）与 `tight_25ms`（12 场）合计 24 场实测中全部满足 `attempted_requests <= 36`、零隔离违规。

## 适用条件、假设与限制

- 外层诊断与规划需占用部分请求配额（在 `B_total=36` 下外层通常占 `15–17` 次，内层 `19–21` 次），在存在偶发代理网络波动时通过离线重试与账本精确核销维持配对可比性。

## 来源及支持的具体结论

- 阶段 3C 双预算四臂 × 三随机种子总报告：`experiments/milestone3/phase3c_four_arm/phase3c_report_standard_500ms.json`、`phase3c_report_tight_25ms.json`。

## 代码和评测关联

- 核心实现：`research_agent/`、`agent_skill_loop/request_budget.py`、`agent_skill_loop/session_runtime.py`。

## 未确认项与冲突证据

- 跨问题扩展（TSP 与在线 OBP）及更高预算曲线（`36 -> 100 -> 200 -> 400`）待后续里程碑 M3.1 与 M3.2 验证。
