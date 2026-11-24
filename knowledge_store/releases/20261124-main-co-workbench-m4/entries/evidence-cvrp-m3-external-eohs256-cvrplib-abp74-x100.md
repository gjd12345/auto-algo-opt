# 里程碑二/三冻结求解器在国际顶会与 OR 黄金标准库 (EoH-S 256 / CVRPLib A·B·P 74 / Set X 100) 外部大考证据

本卡片补充 M2 与 M3 代表冻结求解器在**外部顶会及 OR 黄金标准库**上同一 500 ms 预算、零参数重调的横向验证证据，彻底消除“只在自建小规模分布内自证”的局限。

## 定义或方法步骤

1. **`cvrp_ext_eohs_256`（256 题，EoH-S 协议 `euc_2d_float` vs LKH）**：
   - `i605_cvrp_c1_tworegime`: **`+27.47%`**
   - `cw_parallel_merge`: **`+7.89%`**
   - `cw_relocate_2opt`: **`+6.00%`**
   - `M2 最优 (Arm4b s20261123)`: **`+8.14%`**
   - `M3 最优 (m3_3c_standard_500ms_arm_m3_2_fixed_l2a_s20261126)`: **`+5.91%`**
   - `M3 R2 进化 L3 (m3_3c_standard_500ms_arm_m3_3_r2_l3_evolved_s20261124)`: **`+5.86%`**
2. **`cvrp_ext_cvrplib_abp_74`（74 题，Set A/B/P `euc_2d_nint` vs 官方 `.sol` BKS，双口径报车数合规性）**：
   - `M3 最优 (m3_3c_standard_500ms_arm_m3_2_fixed_l2a_s20261126)`: 整体均 gap **`+4.06%`**（精确-$k$ 合规 `49/74` = `66.2%`，精确-$k$ 子集 gap `+4.11%`），对比 `cw_relocate_2opt` `+4.85%` 与 `C1` `+16.28%`。
3. **`cvrp_ext_cvrplib_x_100`（100 题，Uchoa Set X `n=100..1000` `euc_2d_nint` vs 官方 BKS）**：
   - `M3 最优 (m3_3c_standard_500ms_arm_m3_2_fixed_l2a_s20261126)`: 全体 100/100 合法完成 **`+5.15%`**（分档：`X-S = +5.25%`，`X-M = +5.28%`，`X-L = +4.90%`），对比 `C1` `+15.94%` 与 `cw_parallel_merge` `+6.01%`。

## 适用条件、假设与限制

- CVRPLib A/B/P 官方最优以固定车数 $k$ 为约束，当前通用无车数强限制并行合并求解器以自由车数求得可行解，故同步披露精确-$k$ 合规计数避免指标误读；在 M3.1 跨问题工作中可进一步独立检验 `strict_max_vehicles` 协议。

## 来源及支持的具体结论

- 外部大考汇总：`experiments/milestone3/phase3d_blind_eval/external_benchmarks_report.json`。

## 代码和评测关联

- `agent_skill_loop/interface_design/blind_eval_m3.py`、`tools/run_phase3d_blind_and_release.py`。

## 未确认项与冲突证据

- 在 `X-L (n=501..1000)` 算例上 `relocate_2opt` 单步搜索在 500 ms 下出现合理早停但均保持 100% 合法驻留解返回。
