# CVRP 岛屿流派四：1.1× 相对近邻带节约 + 几何早返 (Island605 C22)

用无量纲相对带宽 1.1*min_d 天然规避了 Frozen C（H-001）混合绝对常数带宽导致的 +206.99% 尺度崩盘，88 题实测 211 次主动早返，是尺度不变带宽门控的正面教科书案例。

## 定义或方法步骤

1. **数学公式**：`mask = (d(i,j) <= 1.1 * min d(i,u)); best = argmax_{j in mask} (d(0,j)-d(i,j)); return 0 if d(i,best) >= d(i,0)`。
2. **旧协议复现**：在 6 月原题（16×n50 Q=40，seed=2024）上精确复算出归档成绩 `12.6100`（旧协议精确 NN 基线 `13.6108`，README 旧注 `13.519`）。
3. **统一工作台表现**：冻结后在全部 10 套 CVRP 考卷上统一分离测时复算完成。

## 适用条件、假设与限制

仍属单车逐点构造范式，在 CVRPLib A/B/P 与 Set X 上仍显著落后于并行 CW 合并与局部搜索；且在 Set A/B/P 上为自由车数求解，需同时查看精确-$k$ 合规率。

## 来源及支持的具体结论

原始归档程序：`experiments/island605_archive/rules/all/cvrp/cvrp_021_E2_highgen_g8_r35__c7e0a7ad.py`（6 月岛屿模型 CVRP 排名第 22）；双轨复现记录：`experiments/milestone15/`。

## 代码和评测关联

已注册至 `SOLVER_CATALOG['i605_cvrp_c22_band_savings']`，哈希与源码锚点已绑定。

## 未确认项与冲突证据

后续方向二可进一步检验该规则并入多规则池后在不同规模与偏心度下的分工贡献。

## EoH 适配

直接通过 `select_next_node` 入口接入 EoH 进化骨架，无需改写底层评测契约。
