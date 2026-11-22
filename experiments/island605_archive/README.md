# island605 归档

2026-06-30 的岛屿模型实验（5×gen8 + 3×gen16 岛并行、种群 6、算子 e1/e2/m1/m2、共享精英池）
共产生 **605 条最佳程序**：TSP 206 / CVRP 207 / BP 192。本目录把它们从原始 jsonl 里整批导出，
**不做 top-k 截断**；去重按"规范化源码 sha256"（逐行 rstrip + 统一结尾换行）进行，实测 0 重复。

## 目录

```
rules/
  all/
    tsp/   <domain>_<rank>_<run_tag>__<sha8>.py    206 条（全量）
    cvrp/                                          207 条（全量）
    bp/                                            192 条（全量）
    manifest.json                                  605 条元数据
  tsp/    island605-T1..T3.py                      9 条代表（每域 top-3，子集指针）
  cvrp/   island605-C1..C3.py
  bp/     island605-B1..B3.py
manifest.json                                      9 条代表的说明
```

- `rules/all/` 是**唯一完整副本**，`rules/<domain>/island605-*.py` 只是便于阅读的 top-3 指针，
  其内容与 `all/` 中对应文件逐字节相同（`python _island_verify.py` 可校验）。
- 文件名里的 `rank` 是该域内按 objective 升序的名次（从 000 开始）。

## 数据来源

`C:\Users\24294\agent_ad-archive-20260710\raw_experiments\agent_go\eoh_rag_workspace\shared_pool\`
下的 `best_codes_{tsp_construct,cvrp_construct,bp_online}.jsonl`（字段 `code/objective/ts`）
与 `pool_index.jsonl`（字段 `problem/run_dir/objective/ts`）。

两文件按**域内位置**对齐（逐行 objective 完全相等，206/206、207/207、192/192），
因此 `run_dir → run_tag` 的归因由位置 join 得到，而不是按 `(objective, ts)` 匹配
（`ts` 含义不同，按键 join 会漏掉 403 条）。

## manifest 字段

`rules/all/manifest.json`：

| 字段 | 含义 |
| --- | --- |
| `domain` / `problem` | `tsp`/`tsp_construct`、`cvrp`/`cvrp_construct`、`bp`/`bp_online` |
| `rank_by_objective` | 域内名次（1 起） |
| `objective` | 原始目标值（TSP/CVRP 为总路程，BP 为比率） |
| `ts` / `run_tag` / `run_dir` | 提交时间与来源 run |
| `sha256` / `path` / `parses` | 规范化源码哈希、相对路径、是否通过 `ast.parse` |

## 口径与注意

- 三个域的目标尺度不同，**不可横向比较**：基线 TSP 6.56、CVRP 13.519、BP 0.0398。
- 605 条来自 **52 个 run 目录**，同一 run 可能贡献多条（不同轮次/不同域），
  且各 run 共享精英池，因此**不能把 605 条当作 605 次独立重复**。
- 这些程序是各自实验框架下的快照，未经过当前 `agent_skill_loop` 评测体系登记；
  若要纳入统一比较，需要用 `canonical 6` 等套件重新评测。

## 复现

```powershell
$env:PYTHONIOENCODING='utf-8'
python _island_export_all.py   # 重新导出 rules/all/ 与 manifest.json
python _island_verify.py       # 校验 9 条代表仍在全量集合内
```

导出结果：`rows_total 605 / kept_total 605 / duplicates_collapsed 0 / parse_failures 0 / meta_unmatched 0 / distinct_runs 52`。
