# 实验脚本目录（experiments）

TOCC 主管线和辅助工具的入口文件。

## 主管线（3 个核心入口）

| 文件 | 用途 | CLI 入口 |
|------|------|----------|
| `eoh_single_runner.py` | **单次 EOH 运行**：构造 RAG context → 调用官方 EOH → 输出 summary.json | `python -m eoh_rag.experiments.eoh_single_runner` |
| `batch_runner.py` | **批量实验运行器**：读 manifest.json → 展开实验矩阵 → 依次调用 single_runner | `python -m eoh_rag.experiments.batch_runner` |
| `problem_registry.py` | **问题定义/题库**：所有问题的 parse 函数和烟雾测试入口 | `python -m eoh_rag.experiments.problem_registry` |

## 网格实验（grids/）

| 文件 | 用途 |
|------|------|
| `grids/arrival_scale_grid.py` | **到达率-密度网格实验**：扫描 problem × density × arrival_scale 组合，支持 RAG 消融对比 |

## 报告生成（reports/）

| 文件 | 用途 |
|------|------|
| `reports/run_summarizer.py` | **运行汇总器**：读取多次 run 的 summary.json → 生成 Markdown 报告 + 卡效果记忆 |
| `reports/rag_ablation_report.py` | **RAG 消融报告**：对比 baseline vs RAG 的逐单元改善率 |
| `reports/arrival_scale_table.py` | 到达率缩放表工具函数（被 grid 和 legacy 共用） |
| `reports/efficiency_table.py` | 效率表工具函数 |

## 其他

| 文件 | 用途 |
|------|------|
| `operator_card_controller.py` | 算子卡控制器入口 → 重导出 `eoh_rag.tocc.controller` |

## legacy/ — 早期脚本

早期实验入口和一次性报告生成器，不被主管线调用，保留用于结果复现。

| 子目录 | 内容 |
|--------|------|
| `legacy/grids/` | InsertShips 网格（dynamic_source_screen、smart_operator_grid、run_selected_repeats） |
| `legacy/reports/` | 论文出图脚本、策略路由探针、早期汇总工具 |
| `legacy/smokes/` | OBP/背包/混载分单的烟雾测试 |

## 数据流

```
manifest.json
    │
    ▼
batch_runner.py  ──────────────────►  eoh_single_runner.py
    │                                      │
    │                                      ▼
    │                                 official_eoh_run_summary.json
    │                                      │
    ▼                                      ▼
reports/run_summarizer.py  ◄──────────────┘
    │
    ▼
报告 + card_outcomes.jsonl
```

