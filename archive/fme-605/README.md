# archive/fme-605 —— FME / EOH-RAG 时代的只读证据档案

本目录保存 2026-06 至 2026-09-08 那条研究线（**FME-RQ1b / 岛屿 605 / Q3 策略卡 / RAG 四臂**）的原始证据与记录。
它**不是**当前主线的一部分，不被任何运行时导入，也不被 `pytest` 收集。

## 来源

全部内容逐字节取自 tag `archive/fme-rq1b`（= 提交 `0efcfc71`，即 `origin/Refactor0830` 的末端）：

```powershell
git checkout archive/fme-rq1b -- evidence agent_records reports/strategy_experiments docs/RESEARCH_MAINLINE.md
```

两个分析文档取自无关历史分支 `feat/data-analysis-plan`（`3740e9d5`，与 main 无 merge-base）：

```powershell
git checkout 3740e9d5 -- docs/eoh-605-analysis-review.md docs/RAG_PAPERS_2026_ANALYSIS.md
```

校验：`MANIFEST.sha256`（295 条 = 294 个研究文件 + 本 README）可用 `sha256sum -c MANIFEST.sha256` 复核。

## 内容

| 路径 | 文件数 | 说明 |
| --- | ---: | --- |
| `evidence/` | 35 | `final_batch_20260630/`（605 次岛屿实验的最终证据包）、`bp_interpretability/` |
| `agent_records/` | 212 | `archive/`(140) `handoffs/`(38) `calibrations/`(13) `contracts/`(11) `knowledge/`(5) `inventories/`(2) `proposals/`(2) `runtime/`(1) |
| `strategy_experiments/` | 44 | Q3 策略卡 v2 完整配对实验 |
| `RESEARCH_MAINLINE.md` | 1 | 作者写的路线总图：唯一活主线 RQ1b、冻结支柱、证据分层规则 |
| `eoh-605-analysis-review.md` | 1 | 605 批次的分析复盘 |
| `RAG_PAPERS_2026_ANALYSIS.md` | 1 | RAG/文献注入路线的阅读笔记 |

## 可直接引用的结果（均出自 `evidence/final_batch_20260630/`）

- 岛屿模型 605 次启动（共享精英池，**非 605 次独立重复**）。
- 去重后头部处方：TSP 6.00393（基线 6.560，−8.48%）、CVRP 12.35639（基线 13.519，−8.60%）、BP 0.00674（基线 0.0398，−83.07%）。
- 全批次中位：TSP 6.213、CVRP 12.859、BP 0.0369；改善 >5% 的批次共 317 次。
- 证据包提交 `e1b90b337d3b6e97e359e03915ab8eedc5f33a8a`；**此后未重跑**。

## 三条禁令（引用前必读）

1. **不得与 RQ1b v2 或 v7 并表**。605 是同预算多岛搜索的历史批次，RQ1b 是同代码行为预测的三臂对照，两者操作定义不同，`mix_cohorts: false`。
2. **RQ1b v1 与 v2 的中断前缀不得引用**。只有 24 单元 × 16 槽的完整续跑（`protocol_hash` 以 `1400431685` 开头）具备完整性；v1（14 完整/4 中断/6 未启动）与 v2 的 12 单元前缀只能报 `partial_integrity_verified`。
3. **本档案无法重放审计**。原始 HTTP 日志、响应与断点落在被 gitignore 的 `outputs/fme_pilot/rq1b_online_20260831_v2{,_resume_v1}`，任何克隆都拿不到；`scripts/audit_rq1b_resume.py` 只能校验本机目录。

## 状态

FME 运行时（`eoh_rag/fme/*`，27 个模块）**未迁入**本仓库主干：`45011029`「Remove historical FME/EoH runtime」已把它们随 940 个文件一并删除，且与现运行时（Skill Runtime + `eoh_frozen`）代号不兼容。需要代码时用：

```powershell
git checkout archive/fme-rq1b -- eoh_rag/fme
```
