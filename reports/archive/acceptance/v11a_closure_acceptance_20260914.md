# v1.1a 闭环验收：2026-09-14

结论：阶段 1 的修复继续落地；阶段 2 执行发现数据门槛阻断，不能宣称
两轮多精英闭环完成。阶段 3–5 未通过，未发起外部付费 API 请求。

## 本轮修复

- Session 事实的公共评测身份在 hash 核验后绑定到 archive 每个候选；候选
  声明冲突时拒绝。此前人工构造的测试带齐字段，掩盖了生产导出空集合。
- Session init 读取 manifest.extra 中冻结的搜索参数；受控 pilot 的
  pop_size、n_pop、max_sample_nums 范围锁定为单值，C/D 不允许另改搜索额度。
- 多 seed 导出使用 seed_N 独立路径，避免所有 seed 竞争同一个目录。
- 保留上一轮的 origin 绑定、逐实例集合评测、发现/成绩引用拆分、预检成本
  和非零失败退出码修复。

## 已执行证据

入口：`tools/verify_benchmark_closure.py`，Windows Python 3.11，真实官方
EoH + localhost fixture + 真实隔离评测器，Memory/repair 关闭。

命令（输出目录必须不存在）：

```powershell
py -3.11 tools/verify_benchmark_closure.py --output outputs/benchmark_closure_new
```

验收不通过时返回 1，并保留证据。不会修改 benchmark 或绕过种群不足门禁。

已保存跑次：`outputs/benchmark_closure_20260914_02/`（本地、gitignored）。

| 项目 | 结果 |
| --- | --- |
| 首轮 solver | 10：baseline 1，generated 9，seed 0，repair 0 |
| 请求 | localhost fixture 10；外部 provider 0 |
| Archive | 9 个不同 code hash；只包含 generated |
| 最终官方种群 | 1 个成员 |
| 第二轮 | insufficient_valid_seeds，task_id=null，未启动 worker |
| Top1 | 从可信 incumbent 资产锁定（本次为 baseline），不冒充生成冠军 |
| archive TopK | 请求 K=10，实际 9 个生成成员 |
| final population | 1 个官方成员 |
| heldout | 三个选集均完整覆盖，fitness=0，仅为 fixture 事实 |
| 重建 | 三份报告从落盘 inputs 重建；selection hash、archive 重建一致 |

文件：`pilot_receipt.json`、`archive.json`、三份 `*.selection.json`、
`*.inputs.json`、`*.report.json` 和 `sha256_manifest.json`。
该跑次尚未覆盖第二轮生成、四组因子隔离或真实模型有效性。

## 阻断原因

对当前 obp_mini 四个训练实例穷举所有合法 feasible-bin 选择，每个实例
可达箱数集合均为 `{3}`，reference 也均为 3。所有合法候选 fitness=0。
固定官方 EoH 的 population_management 按 objective 去重，因此种群最多
一个成员；population size 最低为 2。增加请求或换模型无法解除这个限制。

下一项必须是数据决策：保留现有 obp_mini/hash 作为历史接线资产，另建
有合法策略成绩差异的新版本 mini profile，再冻结资产、gold 和 manifest。
不能修改已有冻结数据，不能悄悄改官方去重或补冷启动来通过验收。
新 profile 应先验证可达成绩差异和官方最终种群规模，然后重跑两轮门槛，
再进入 A/B/C/D fixture 与真实 pilot。

## 验证范围

- Python 3.11 benchmark kernel：21 passed（含真实事实形状 archive 和
  manifest 到 Session 参数接线回归）。
- 本轮较早的 benchmark + spawn provenance：24 passed。
- compileall 与 diff 检查通过。
- 尚未重跑最终改动的全仓、Linux/WSL、wheel 发布矩阵；这些不是已通过项。

未创建 release candidate，未 commit/push；用户的 knowledge_* 与历史
session_preflight 目录未修改。
