# TOCC/RAG Experiment Outcomes — 按问题整理

本目录按 **问题维度** 整理 TOCC + RAG 实验的最优结果和对比分析。

## 目录结构

```
outcomes/
├── README.md                     # 本文件
├── tsp_construct/
│   ├── best_results.md           # TSP 最优结果汇总 + 对比表
│   └── best_code.py              # 历史最优代码
└── cvrp_construct/
    ├── best_results.md           # CVRP 最优结果汇总 + 对比表
    └── best_code.py              # 历史最优代码
```

## 数据来源

- `auto_experiment_reports/tocc_stabilization_repeats/` — 跨臂对比（gen=0, pop=4, repeat=3）
- `auto_experiment_reports/tocc_day1_cvrp_repeat5/` — CVRP init-only repeat=5
- `auto_experiment_reports/tocc_day2_tsp_*` — TSP gen=4 对比（pure vs tocc vs real_evolution）
- `auto_experiment_reports/tocc_day2_cvrp_real_evolution_gen4/` — CVRP gen=4 进化
- `auto_experiment_reports/tocc_best_code_records.md` — 历史最优代码归档

## 核心结论

| 问题 | 指标 | pure_eoh | tocc_corrected | 提升 |
|------|------|----------|----------------|------|
| TSP (gen=0) | best | 6.590 | **6.189** | -6.1% |
| TSP (gen=4) | best | 6.269 | **6.217** (V2 agent) | -0.8% |
| TSP (gen=4) | mean | 6.548 | **6.456** | -1.4% |
| CVRP (gen=0) | best | 13.279 | **12.713** | -4.3% |
| CVRP (gen=4) | best | 13.146 | **12.705** | -3.4% |
| CVRP (gen=0) | mean | 13.550 | **12.975** | -4.2% |

**关键发现**: TOCC targeted RAG（regret + farthest cards）在 CVRP 上稳定优于 pure_eoh 4%+，在 TSP 上 gen=4 有 1-6% 的提升但方差较大。
