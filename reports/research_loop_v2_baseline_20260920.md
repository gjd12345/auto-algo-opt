# 研究闭环 v2 基线清单

本清单在隔离 worktree 中建立，目标是保留原工作区的全部在途工作，并说明哪些材料可用于
本里程碑。记录日期为 2026-09-20。

## 代码身份

- 隔离基线：`74a1fb8b3b747a2113426e90315dc170039a0f60`（Complete CO iteration B real pilot）。
- 父提交：`e310ff42e512314d9ed9fbcb80dd2ae99532780b`（Implement CO iteration B search progress）。
- 原工作区 HEAD：`3a15c2ad2f5c382a21e40ca547a5c7c810db736a`。
- 原工作区相对审查基线落后两个提交：`e310ff4`、`74a1fb8`。
- 本实现分支：`codex/research-loop-v2`，从上述完整 `74a1fb8...` 建立。

## 原工作区的三项已跟踪修改

| 文件 | diff 规模 | 工作文件 SHA-256 | diff SHA-256 | 本里程碑处置 |
|---|---:|---|---|---|
| `extensions/optics/src/artifact_session/runner.py` | +74/−2 | `34b2f1c438329440e493d374b2c66571e0bac69587b158a09a8f9a25ec189f04` | `22c8b54c4b53e9ec50235b1d054fe3f4f558f4130d7ed196be7fcd519941226d` | 保留在原工作区，不进入 OBP 研究闭环 |
| `extensions/optics/src/optics_backend/worker.py` | +12/−6 | `94a98abaf64d7d441bed4530afc7379a6e827e778d000751435b8acd0849e02b` | `494acefda48ecef8e3970d656472170df0987edcbcf3021b80f38805ee2840ce` | 保留在原工作区，不进入 OBP 研究闭环 |
| `tools/export_benchmark_evidence.py` | +23/−0 | `a03521e71b7a068e1fd0907fbb12a39a4b7dd1921cab4309dc2bed85aaa1f9f7` | `f0560fece86a0926f424a86e1198a0b9e03ba208bf2611114f3cb6c88620eaa2` | 只作参考；在隔离基线上按新证据合同重新实现 |

未对原工作区执行 checkout、reset、clean、stash 或文件写入。

## 未跟踪材料

原工作区包含未跟踪的 pilot 报告、compact evidence、系统清单、临时工具、测试和本地 skill
链接。它们全部保留原位，没有整批复制或提交。主要类别为：

- `reports/evidence/` 下的历史 compact bundles；
- `reports/d1_pilot_20260915/`、`reports/archive/pilot_pre_correction_20260915/`；
- `tools/prepare_agent_pilot.py`、`tools/run_controlled_pilot.py`、
  `tools/assemble_controlled_pilot_report.py` 等原型；
- `tests/kernel/test_pilot_corrections.py` 和若干人读报告；
- `.grok/` 本地 skill 链接。

这些材料可帮助定位历史主张，但“未跟踪”不等于可信证据。只有包含在可验 hash 清单中的
文件才能被新报告直接引用。

## 历史证据分级

| 等级 | 判定规则 | 本次处理 |
|---|---|---|
| 可验证 | 原始文件存在、身份与 SHA 可闭合、数字可从 bundle 重建 | 只作为历史事实输入，不自动成为新实验结果 |
| 待复核 | 有报告或部分产物，但缺 Session/精确来源链 | 明确标为待复核，不补跑推断 |
| 缺失 | 报告数字没有可取得的原始 Session 或 bundle 文件 | 降级为“未独立复核” |

按冻结决定，本阶段不补跑历史实验。设计示例单独标记为 `design_example`，不能伪装成历史证据。

## 纳入与排除

- 纳入：OBP Session 合同、精确身份、comparison packet、研究笔记引用、run 内 Memory、
  controller/provider 成本与证据导出。
- 排除：两项 optics 修改；TSP/CVRP/TSP2OPT behavior contract；正式 heldout 评测；
  对未跟踪 pilot 产物的批量提交。
- heldout 在诊断阶段保持锁定。
