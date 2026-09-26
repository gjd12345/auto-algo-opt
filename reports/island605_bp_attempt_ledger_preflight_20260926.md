# island_605 BP：第二次工程试跑停止记录

2026-09-26，`outputs/island605-bp-abc-diagnostic-20260926-v3/` 的首个配对 seed (`1836735484`) 完成 A/B/C 第一轮后立即停止。其余两个 seed 的六个 Session 只完成初始化和共同首轮 Plan，也已全部标记 `STOPPED`，没有 EoH 请求或 solver 调用。v3 九个 Session 均不进入 A/B/C 诊断结果。

首个 seed 的 A/B/C 各使用 25 次 solver 调用。A 的训练侧 incumbent 为 0.038535063890，B 为 0.025757118422，C 为 0.012878559211。A 的第 25 次调用在轮预算耗尽时中断，没有形成可评测候选；旧 `attempt_trace` 从 `candidates` 列表构造，故只看到 24 条，错误给出 `insufficient_window`。这是预算账本与停滞判断的工程缺陷，不是 A 组的真实停滞或处理效果。三组首轮质量数值不能作为确认性 A/B/C 比较。

修复后，轨迹从 SQLite `solver_calls` 按记录顺序构造，通过 `evaluation_id + code_sha256` 精确关联已有候选。中断调用保留身份和尝试位置，质量沿用此前 best，不伪造 objective。针对旧 v3 原始账本作只读离线重算，A/B/C 各有 25 条可完整对账的尝试轨迹；中断数分别为 1/0/0，三组均正确判为 `progress`。A 的冻结窗口绝对增益为 0.001307978670。原始 Session、首轮停滞结果和证据文件没有被重写，离线重算只验证修复行为。

首 seed 三个停止运行各导出 16 文件的精简证据包，逐文件 SHA-256 校验通过，位置为 `outputs/island605-bp-abc-diagnostic-20260926-v3/bundles/seed_1836735484/{A,B,C}/`。v3 的 Runtime 身份与修复后的代码不同，后续实验必须从新清单与新 Session 开始。v2 和 v3 的费用均单列为工程试跑成本，不并入正式九运行分析；heldout 未读取。
