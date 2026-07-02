# 后续实验规划

**日期**: 2026-06-09
**状态**: 待执行
**前置条件**: Goal §5.4 算子规则已生效，所有新实验必须用 `e1,e2,m1,m2`

---

## 一、当前状态总结

### 已有数据（全部 i1-only，无真正进化）

| 问题 | Arm | n | mean | best | 备注 |
|------|-----|---|------|------|------|
| CVRP | pure_eoh | 10 | 13.550 | 13.279 | 稳定 |
| CVRP | tocc_corrected | 8 | 12.975 | 12.713 | 5/5 一致优于 pure |
| CVRP | default_rag | 5 | 13.283 | 13.283 | 全部相同值（degenerate） |
| TSP | pure_eoh | 6 | 6.610 | 6.269 | 方差大 |
| TSP | tocc_corrected | 8 | 7.137 | 6.189 | 9.66 outlier 拉高均值 |

### 已发现的问题

1. **所有实验都是 i1-only**：8 个 manifest 全部 `operators="i1"`，没有 crossover/mutation
2. **CVRP tocc 优势稳定**：8 次运行中 tocc 全部优于 pure（i1-only 对比公平）
3. **TSP tocc 方差极大**：6.19 到 9.66，outlier 原因未知
4. **default_rag degenerate**：CVRP 上 5 次全部 13.283，说明默认 RAG 没有帮助

### 待验证假设

| 假设 | 验证方法 | 优先级 |
|------|----------|--------|
| H1: TOCC cards 在真正进化下仍优于 pure | 用 e1,e2,m1,m2 跑 TSP/CVRP | P0 |
| H2: cards 帮助 crossover 产生更好后代 | 对比 i1-only vs e1,e2,m1,m2 的进化轨迹 | P0 |
| H3: TSP outlier 与 init 质量相关 | 诊断 9.66 run 的 init population | P1 |
| H4: 更大 pop_size 缓解方差 | pop=8 对比 pop=4 | P2 |

---

## 二、实验计划

### Phase 1: 真正进化验证（P0，夜间执行）

#### Exp 1.1: TSP 真正进化（已创建 manifest）

```bash
# manifest: tocc_day2_tsp_real_evolution_gen4.json
# operators: e1,e2,m1,m2
# arms: pure_eoh vs tocc_corrected
# gen=4, pop=4, repeats=3, 24 samples/run
```

**目的**: 验证 H1——TOCC cards 在真正进化下是否仍优于 pure

**预期结果**:
- 如果 tocc 仍然优于 pure → cards 在进化场景下有效
- 如果 pure 反超 → cards 只对 init sampling 有效，对进化有害
- 如果无差异 → cards 效果不显著

**对比基线**: tocc_day2_tsp_pure_gen4 (i1-only, n=3) 和 tocc_day2_tsp_tocc_gen4 (i1-only, n=3)

#### Exp 1.2: CVRP 真正进化

```json
{
  "suite": "tocc_day2_cvrp_real_evolution_gen4",
  "model": "JoyAI-LLM-Pro",
  "problems": ["cvrp_construct"],
  "arms": [
    {
      "name": "pure_eoh",
      "runner_arm": "pure_eoh",
      "context_strategy": "none",
      "problems": ["cvrp_construct"]
    },
    {
      "name": "tocc_corrected",
      "runner_arm": "literature_rag",
      "context_strategy": "tocc_selected_cards",
      "rag_query": "cvrp construct regret far first capacity",
      "selected_card_ids": ["cvrp_regret_insertion", "cvrp_far_first"],
      "problems": ["cvrp_construct"]
    }
  ],
  "generations": [4],
  "pop_size": 4,
  "repeats": 5,
  "max_runs": 10,
  "max_llm_calls_estimate": 240,
  "require_confirm_for_real_run": true,
  "operators": "e1,e2,m1,m2",
  "run_timeout_s": 7200,
  "rag": { "top_k": 2, "max_chars": 2500 },
  "python_exe": "python3",
  "official_root": "official_eoh"
}
```

**目的**: 验证 H1 在 CVRP 上——i1-only 下 tocc 5/5 全赢，进化下是否仍然一致

**对比基线**: tocc_day1_cvrp_repeat5 (i1-only, n=5)

#### Exp 1.3: i1-only vs 进化对比（同问题同 arm）

**目的**: 验证 H2——cards 是否帮助 crossover 产生更好后代

设计：用同一个 tocc_corrected arm，分别跑 i1-only 和 e1,e2,m1,m2，对比：
- init 质量（应该相同，因为 init 始终用 i1）
- gen1-gen4 的改善幅度（进化应该有额外改善）
- 最终 best（进化应该更好）

这个对比不需要新实验——用 Exp 1.1 的结果与已有 tocc_day2_tsp_tocc_gen4 对比即可。

---

### Phase 2: TSP Outlier 诊断（P1，白天执行）

#### Exp 2.1: 诊断 9.66 outlier

**目的**: 理解 tocc_stabilization_repeats 中 TSP r1 为什么出现 9.66

**方法**:
1. 读取 `tocc_stabilization_repeats/run_tsp_construct_tocc_corrected_r1/` 的 run_log
2. 检查 init population 的 8 个样本的 fitness 分布
3. 检查是否是 eval 超时、代码 bug、还是 LLM 生成了差代码
4. 对比 r3 (6.19) 的 init population

**预期产出**: outlier 根因报告

#### Exp 2.2: TSP init 分布分析

**目的**: 理解 TSP 上 tocc init 的方差来源

**方法**:
1. 汇总所有 TSP tocc 的 init best（n=8）：7.94, 6.40, 6.60, 6.55, 7.45, 9.66, 7.01, 6.19
2. 分析 init 代码差异——哪些策略被 LLM 正确实现，哪些失败
3. 检查 RAG cards 是否在某些 run 中被截断或丢失

---

### Phase 3: 扩展验证（P2，条件执行）

#### Exp 3.1: 更大 pop_size

```json
{
  "suite": "tocc_tsp_real_evolution_pop8",
  "operators": "e1,e2,m1,m2",
  "pop_size": 8,
  "generations": [4],
  "repeats": 3
}
```

**目的**: 验证 H4——更大 pop 是否缓解方差
**条件**: 仅在 Phase 1 显示 tocc 在 pop=4 下有效时执行

#### Exp 3.2: 更多 repeats

**目的**: 统计显著性
**条件**: 仅在 Phase 1 显示 promising signal 时执行
**设计**: TSP/CVRP 各 10 repeats，e1,e2,m1,m2

#### Exp 3.3: 新问题迁移

**目的**: 验证 TOCC 在新问题上的泛化
**候选问题**:
- Knapsack（已有 smoke 数据）
- FJSP（A2DEPT 用了此问题）
- MIS（CO-Bench 和 A2DEPT 都用了）

---

## 三、执行时间表

| 阶段 | 实验 | 预计耗时 | 执行时间 | 状态 |
|------|------|----------|----------|------|
| Phase 1.1 | TSP 真正进化 | ~2h | 今晚 | 待跑 |
| Phase 1.2 | CVRP 真正进化 | ~3h | 今晚 | 待创建 manifest |
| Phase 2.1 | 9.66 outlier 诊断 | ~30min | 明天白天 | 待执行 |
| Phase 2.2 | TSP init 分布分析 | ~30min | 明天白天 | 待执行 |
| Phase 1.3 | i1 vs 进化对比 | 0 (用已有数据) | 明天白天 | 待分析 |
| Phase 3.1 | pop=8 扩展 | ~4h | 条件执行 | 待定 |
| Phase 3.2 | 更多 repeats | ~6h | 条件执行 | 待定 |
| Phase 3.3 | 新问题迁移 | ~4h | 条件执行 | 待定 |

---

## 四、预期产出

### 每个实验必须产出

1. **summary.md** — 自动生成
2. **run_index.json** — 自动生成
3. **best code record** — 记录每个 arm 的最佳代码
4. **evolution trajectory** — 记录每代 best fitness 变化
5. **operator usage stats** — 记录每个算子（e1/e2/m1/m2）被选中的次数和对应的 improvement

### 汇总报告

实验完成后写入 `eoh_rag_workspace/reports/auto_experiment_reports/real_evolution_report.md`：
- i1-only vs e1,e2,m1,m2 对比表
- TOCC cards 在进化场景下的效果
- TSP outlier 根因
- 统计显著性评估

---

## 五、禁止事项

```text
1. 不再创建 operators="i1" 的新实验（除非是 init-only 烟雾测试）
2. 不在报告中使用 "evolution" 描述 i1-only 实验
3. 不在 n<5 时写 "稳定优于"
4. 不忽略 outlier——必须诊断后决定是否排除
5. 不把 default_rag degenerate 值（13.283）当作 RAG 效果
```

---

## 六、论文叙事更新

基于文献调研和实验修正，论文叙事调整为：

### 可以说

```text
1. TOCC 是 trace-conditioned card selection，与 CoEvo-AHD（工具增强）正交可组合
2. CVRP 上 tocc_corrected 在 i1-only 下 8/8 优于 pure（mean 12.98 vs 13.55）
3. TOCC cards 改变了 LLM 生成的代码结构（regret + farthest 策略出现）
4. 真正进化实验正在进行中
```

### 不可以说

```text
1. "TOCC 提升了进化质量"（未验证）
2. "TSP 上 TOCC 稳定优于 pure"（方差太大）
3. "cards 帮助 crossover 产生更好后代"（未验证）
4. "统计显著"（n 太小）
```

### 论文定位

```text
TOCC 的贡献：
1. 实验控制原语（manifest runner / gatekeeper / summarizer）
2. trace-conditioned card selection（基于执行轨迹的策略卡选择）
3. 与 CoEvo-AHD 正交可组合（cards + tools）
4. 轻量级知识注入（不需要 RL 微调，不需要生成可执行代码）
```
