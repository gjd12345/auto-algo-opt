# Stage-2 autonomous math discoveries synthesis (H-004 to H-009)

汇总第二阶段 8 轮自主数学分析（`s2_autonomous_math_r8`）中提出、消融并验证的六项递进数学机理（`H-004`–`H-009`）。

## 定义或方法步骤

1. **`H-004`（无量纲主动早返仓）**：当最佳候选的归一化节约率 $\sigma(i,j) = 1 - \rho(i,j) < \tau$ 时主动返回 `0`，避免跨仓库无效桥接，并校准 $\beta_{\text{fill}} \in [0.05, 0.18]$ 防止容量项压过几何项。
2. **`H-005`（三角伸长比 $\rho$ 与自适应早返）**：将线性的 `(d_cur - alpha*d_dep)/scale` 与无量纲伸长比 $\rho(i,j) = d(i,j)/(d(0,i)+d(0,j))$ 融合，实测 `ana72` 降至 `18.296`。
3. **`H-006`（两阶段剩余车队出发 `rem_routes` + 余弦角花瓣相干 $\cos\theta_0$）**：通过 `rem_routes = sum(q)/rest_cap` 在外围清扫与核区收尾间平滑切换，叠加余弦定理角相干抑制跨扇区跳跃，`ana72` 进一步降至 `17.927`（R4 在 `P0-120` 达 `19.8100`）。
4. **`H-007`（纯状态内旋 $\alpha_{\text{eff}}(\text{pressure})$）**：与被证伪的逐候选末端惩罚 `H-004a` 相反，使用同步对所有候选统一的车辆压力 `pressure = min(1, mean(q_F)/rest_cap)` 驱动 $\alpha_{\text{eff}} = \alpha_0 - \alpha_1 \cdot \text{pressure}$，消除反重货偏置并产出最优规则 `R5`（`P0-120 = 19.6092`）。
5. **`H-008`（AST 安全孤立紧迫度 $-w_{\text{iso}} d_{\text{nn}}$ + 无硬门槛早返）**：以 `np.where(np.eye(n)>0.5, np.inf, sub)` 修复 R6 的 `fill_diagonal` 拒绝，产出在聚类工况胜场最高的 `R7`（`s2_r7_iso`）。
6. **`H-009`（实现缺陷审计与后期边际递减）**：定位 R7 源码中 `pressure = 0.0` 硬编码及候选 1/5 `sum(dem)` 饱和缺陷，透明记录 R8 后期边际递减。

## 适用条件、假设与限制

- 多组件在最终规则 `R5 / R7` 中协同作用，目前由逐轮单步离线消融证据支撑，尚未做全 $2^5$ 子集全因子拆解。
- 来源于单次配对搜索（48 EoH 请求/臂，实验臂 Token 多约 35% 且单列外部分析成本）。

## 来源及支持的具体结论

- 完整假设账本：`experiments/cvrp_midterm/ledger/hypotheses.jsonl`（条目 `H-004` 至 `H-009`）。
- 盲测与全新独立验收集数据：`experiments/cvrp_midterm/analysis/s2_holdout_eval.json`、`results/summary.json`。

## 代码和评测关联

- 关联规则卡：`method-cvrp-s2-r5-spiral`、`method-cvrp-s2-r7-iso`；关联证伪反例卡：`evidence-cvrp-antipattern-falsified-hypotheses`。

## 未确认项与冲突证据

- 多随机种子独立搜索的方差尚未统计，计划在里程碑三无人值守 Research Agent 中补齐多 seed 对照。
