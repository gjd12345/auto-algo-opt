# 问题目录、已注册 Benchmark 与实验数据套件入口说明

本文明确区分仓库内**三类不同层级的入口**，避免将研究诊断或实验数据套件误读为已注册的可执行 Benchmark。

---

## 一、`ProblemSpec` 代码契约入口

位置：`agent_skill_loop/problems/`（注册表见 `agent_skill_loop/problems/base.py:PROBLEM_REGISTRY`，通过 `get_problem(problem_id)` 获取）。

`ProblemSpec` 定义进化入口签名、提示模板、沙箱能力白名单（AST / NumPy / Math 允许列表）与正式评测语义（CVRP 正式评测见 `agent_skill_loop/evaluator.py`）。当前已注册 5 个 `ProblemSpec`：

| `problem_id` | 进化入口函数 | `interface_version` | 简要说明 |
|---|---|---|---|
| `cvrp_construct` | `select_next_node` | `v1` | 单车顺序构造 CVRP（允许合法主动早返仓 `return 0`） |
| `obp_online` | `priority` | `v1` | 1D 在线装箱（EoH-S 协议接口） |
| `bp_online_island605` | `score` | `archive-restored-v1` | 归档恢复的 1D 在线装箱历史接口 |
| `tsp_construct` | `select_next_node` | `v1` | TSP 顺序构造 |
| `tsp_2opt` | `select_2opt_move` | `v1` | TSP 2-opt 邻域移动选择 |

---

## 二、已注册 Benchmark 入口（`benchmarks/eohs_v1/registry.json`）

加载入口：`agent_skill_loop/benchmark/catalog.py:load_profile_suite(benchmark_id, profile, split=...)` 与 `benchmark_profile(benchmark_id, profile)`。所有清单文件在加载时强制校验 SHA-256 与 `metric_spec_hash`。

| `benchmark_id` | `profile` | `problem_id` | `dev_train` / `train` | `heldout` / `test` 策略 |
|---|---|---|---|---|
| `eohs_v1` | `obp_mini` | `obp_online` | 4 例再生协议兼容训练夹具 | 可读取（`obp_mini_test.json`） |
| `eohs_v1` | `obp_evolution_mini` | `obp_online` | 6 例确定性已知最优训练集 | 可读取（`obp_evolution_mini_test.json`） |
| `eohs_v1` | `obp_search_mini` | `obp_online` | 6 例确定性已知最优搜索集 | 可读取（`obp_search_mini_test.json`） |
| `island605_bp` | `historically_exposed_train_v1` | `bp_online_island605` | 5 条历史暴露训练流 | `locked_no_access_diagnostic`（抛出 `ValueError("heldout_locked_no_access")`） |
| `eohs_v1` | `cvrp_construct_mini` | `cvrp_construct` | **4 例 `n=50` 开发训练集**（`manifests/cvrp_construct_mini_train.json`） | **`locked_no_access_diagnostic`（抛出 `ValueError("heldout_locked_no_access")` 属预期行为）** |

读取 `cvrp_construct_mini` 4 例训练套件的标准方式：

```python
from agent_skill_loop.benchmark.catalog import load_profile_suite

train_suite = load_profile_suite("eohs_v1", "cvrp_construct_mini", split="dev_train")
assert len(train_suite["instances"]) == 4
# 访问 split="heldout" 或 split="test" 触发 ValueError("heldout_locked_no_access")，
# 这是防泄露锁的预期行为（该 profile 未注册独立 heldout）。
```

---

## 三、实验数据套件入口（非 Benchmark 注册项）

以下套件位于实验或冻结证据目录，不属于 `benchmarks/eohs_v1/registry.json`，按明确用途分工使用：

| 套件名称 | 生成或加载入口 | 规模与构成 | 定位与用途 |
|---|---|---|---|
| **搜索开发集 `dev4`** | `load_profile_suite("eohs_v1", "cvrp_construct_mini", split="dev_train")` | 4 例（`n=50`） | EoH 搜索期内部适应度评估；样本极小，单凭其选优存在跨规模过拟合风险（如 `auto_dev1_r3`） |
| **共享诊断集 `shared_diagnostic_6` (`sh6`)** | 只读加载 `reports/evidence/cvrp_super_agent_reference_20261107/dev_suite.json`（经 `experiments/cvrp_midterm/runs/round_activity.py`） | 6 例（**包含 `dev4` 全部 4 个搜索期实例 + 2 例补充**），`C = 10.9197` | 搜索过程与尺度敏感性（`s=1` vs `s=1e-3`）开发诊断，**不作为独立盲测集** |
| **离线边界分析与选优集 `ana72`** | 确定性生成：`experiments/cvrp_midterm/analysis/boundary_analysis.py`（种子 `20261123`） | 72 例（`n ∈ {50, 100, 200}` × `{uniform, clustered}`，`Q=40`） | H-003 仓库出发步相变扫描、反事实置换及零 P0 泄露的候选规则筛选（如选出 `s2_r5_spiral`） |
| **独立盲测集 `P0-120`** | 只读加载 `reports/evidence/cvrp_p0_p1_p2_20261107/p0/suite_{50,100,200}.json`（经 `experiments/cvrp_midterm/analysis/eval_s2_holdout.py`） | 120 例（`n=50/100/200` 各 40 例，冻结只读） | 方向一规则的独立多规模盲测与配对 Bootstrap 检验；**全程未参与搜索与选优** |
| **多因子异构选择矩阵 `hetero-288`** | 确定性生成：`experiments/cvrp_midterm/selection_s2/run_matrix_s2.py`（种子 `20261122`）；选择评估：`selection_s2/select_s2.py` | 288 例（5 因子：`size ∈ {50,100,200}` × `spatial` × `depot` × `capacity` × `demand_dist`，48 工况 × 6） | 方向二候选池互补性分析（VBS/SBS）、与 `cw_merge` 参照对比及折外选择器验证（`cv12` / `loro48` / `loso3`） |
