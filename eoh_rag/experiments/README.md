# 实验脚本目录（experiments）

Refactor0830 的科学控制器在 `eoh_rag.fme`，不在本目录的 EOH 批量循环里。
EOH 只生成候选，RAG 只提供开发域证据，都不能代替 `FMEResearchLoop` 选择科研动作。

本目录提供两类东西：当前 FME 在线入口，以及历史 EOH 复现适配器。

## 当前入口

| 文件 | 用途 | CLI |
|------|------|-----|
| `fme_pilot.py` | RQ1–RQ4 三问题在线对照：默认只冻结协议 | `python -m eoh_rag.experiments.fme_pilot` |
| `../fme/rq1b_v2.py` | 当前聚焦的 RQ1b：CVRP 三臂行为分析 | `python -m eoh_rag.fme.rq1b_v2` |

```bash
# 只冻结，不调 API；必须用全新输出目录
python -m eoh_rag.fme.rq1b_v2 --output outputs/fme_pilot/rq1b_prepared_new
python -m eoh_rag.experiments.fme_pilot --output outputs/fme_pilot/prepared

# 只读审计，不调模型、不跑 solver
python scripts/audit_rq1b_resume.py outputs/fme_pilot/rq1b_online_20260831_v2_resume_v1 --output outputs/rq1b_resume_audit_recheck.json
```

RQ2 历史、RQ3 迁移、RQ4 模型比较和 Phase 6 已暂停。未经新授权不要 `--execute`。

## 历史复现（不是新证据）

| 文件 | 用途 | CLI |
|------|------|-----|
| `batch_runner.py` | 读历史 manifest，展开矩阵，调用单次 EOH | `python -m eoh_rag.experiments.batch_runner` |
| `eoh_single_runner.py` | 单次官方 EOH：可选注入 RAG 上下文 | `python -m eoh_rag.experiments.eoh_single_runner` |
| `official_eoh_run.py` | `eoh_single_runner` 的别名 | 同上 |
| `problem_registry.py` | 三个主线问题的解析与烟雾入口 | `python -m eoh_rag.experiments.problem_registry` |

`grids/` 现仅有包占位，不再提供 `arrival_scale_grid.py`。
旧 TOCC、selector、expert-router 只用于复现，不进主线注册表。

## 支持模块

| 文件 | 用途 |
|------|------|
| `provider.py` | OpenCode Go 等供应商配置与预检 |
| `research_contracts.py` | FME 候选 / 评测 / 主张的冻结数据类 |
| `baselines.py` | 官方 EoH 基线常量 |
| `evaluator.py` | 历史 EOH 目标值相对基线的决策 |
| `pool_api.py` | 岛屿模型共享池 |
| `rag_context_builder.py` | 历史 EOH 路径的检索上下文 |
| `hooks.py` / `run_tracker.py` | 抽出的副作用与元数据 API；batch 路径未接线 |

## 报告脚本（reports/）

| 文件 | 用途 |
|------|------|
| `run_summarizer.py` | 读取多次 EOH summary，生成 Markdown |
| `summarize_rag_ablation.py` | RAG 消融汇总 |
| `summarize_manifest_runs.py` | manifest 运行索引汇总 |
| `export_strategy_evidence.py` | 策略卡实验可提交证据导出 |
| `analyze_q3.py` / `analyze_*cvrp*` / `analyze_bp_fme_pilot.py` | 历史分析，不改变正式门槛 |

## 数据流

```
当前：
  refactor0830_rq1b_v2.json  →  eoh_rag.fme.rq1b_v2  →  EvidenceJournal / held-out
  refactor0830_opencode_go_pilot_v7.json  →  fme_pilot  →  FMEResearchLoop

历史复现：
  manifest.json  →  batch_runner  →  eoh_single_runner  →  official_eoh_run_summary.json
```

