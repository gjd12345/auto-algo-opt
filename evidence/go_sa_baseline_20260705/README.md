# Go 派船调度 · SA 基线网格(J_SA)· 2026-07-05

论文《Real-time Routing … via LLM-assisted Heuristic Design》里 Guarded EOH-Go 的对照参照。
`J_SA` = 模拟退火种子解 `InsertShips`(即 `go_solver/main.go` 原始实现)在 Solomon RC 数据集上的路由总成本。

## 单元
RC101–105 × 密度 d{25,50,75} × 到达时间缩放 t∈{1.0,0.9,0.8,0.7,0.6} = **75 单元**。
目标 `J + 0.2·Res`(J = final cost 路由总成本,Res = 进程墙钟秒)。

## 复现
```bash
cd Agent_EOH/eoh/src/eoh/examples/user_insertships_go
python3 run_sa_baseline_grid.py \
  --output-dir <out> --densities d25,d50,d75 --scales 1.0,0.9,0.8,0.7,0.6 \
  --repeats 3 --instances 5 --sim-time-multi 10 --run-timeout-s 60
python3 summarize_sa_baseline.py --results-dir <out>   # 可选 --archive-ref <ref.json> 做核对
```
种子解注入 `go_solver/main.go` 后编译一次(`mainbin_sa`),逐格串行运行(保证 Res 不受并发干扰),
每格重复 3 次取中位;超时即判该格病态并跳过其余重复。

## 结论
- **65/75 单元得到 J_SA**;J 跨重复 63/65 完全确定(仅 RC105 d25 t0.7 双峰)。
- **RC103 d25/d50(10 单元)病态**:SA 不收敛,>60s 超时(200s 探针仍未完成)→ 有效对比网格 = **65 单元**(RC103 仅 d75 可用)。
- 与历史归档核对:61/65 完全一致,4 个可解释(2 个随机单元 + 2 个归档欠采样)。

## 文件
- `sa_baseline_summary.csv` — 每格聚合(J_median/mean/std/min/max、Res、composite、n_ok、timed_out)。
- `sa_baseline_cells.csv` — 每次重复一行(J、Res、composite、return_code、timeout)。
- `sa_baseline_results.json` — 完整结构化结果 + config。
- `sa_baseline_report.md` — 覆盖率 / 随机性 / 核对 / 各密度概览。
