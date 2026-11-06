# Changelog

本文件记录对外可引用的版本。每条都标注证据强度：**已提交且可复算** / **限条件** / **未执行**。

## v1.2.0 —— 2026-11-06 · 主干收敛版

主题：把四条研究支线收敛成一条可发布的主干，并把已退出主线的资产降为只读档案。

### Added

- `archive/fme-605/` —— FME/EOH-RAG 时代（tag `archive/fme-rq1b`，`0efcfc71`）的只读证据：`evidence/` 35 文件、`agent_records/` 212 文件、`strategy_experiments/` 44 文件、`RESEARCH_MAINLINE.md` 与研究笔记，附 `MANIFEST.sha256`。
- `archive/optics/` —— 光学线的文档、P0–P5 验收与删除前的工作区补丁，附恢复命令。
- `archive/thesis/` —— 岛屿 605 图文与年度报告进展二（13 文件 + `MANIFEST.sha256`）。
- `tests/kernel/test_heldout_behavior_scope.py` —— 固定 held-out 不携带 training 侧行为证据。

### Changed

- **主线定义**：`Coding Agent`（认知）· `Session Runtime`（状态/预算/恢复）· 官方 `EoH`（轮内进化）· `Deterministic Evaluator`（裁决）四权分立；`SQLite` 为唯一可变控制面权威。
- `integration/thesis-core` 以 `27442cb7` 为起点（`3a15c2ad`、`74a1fb8b`、`1d4608a8` 均为其祖先，零冲突）。
- CI 触发改为 `main` + `integration/**`，删除 `optics` job。

### Removed

- `extensions/optics/`（109 文件）及其 CI、测试、依赖与文档入口；六镜牛顿（`six_mirror_*`）随之退出主干（它的代码只存在于 tag `archive/six-mirror`）。
- `README` 的"光学设计"路线与快速开始，改为单主线叙事 + 归档说明。

### Fixed

- **R01（P0，来自 2026-10-04 独立评审）**：`agent_skill_loop/evaluator.py` 现在只在 `split ∈ {train, dev_train}` 时附带 `behavior_evidence`；held-out 全量评估与 partial 收集都不再产出该字段，objective 不受影响。
- `test_memory_kernel_lock_released_after_owner_killed` 不再与内核抢跑：Windows 在被杀进程回收后数百毫秒才释放字节锁，测试改为等待锁释放（上限 5s）。

### Verified（本地，Windows · Python 3.11.9）

- `pytest tests/kernel tests/knowledge tests/eoh_frozen` → **257 passed, 12 skipped**。
- `python -m compileall agent_skill_loop eoh_frozen knowledge_tools skills tests tools` → 通过。
- **未验证**：`tests/eoh_frozen` 的 10 个 skip 需要官方 EoH（`pip install -e ".[eoh]"` + `EOH_REQUIRED=1`）；Linux 3.11 未在本机执行；wheel 外部安装未重跑。

### 事实边界（引用本版时必须带上）

- 岛屿 605（TSP −8.48% / CVRP −8.60% / BP −83.07%）是历史批次、共享精英池，**不是当前主干代码可复现的结果**，且不得与 RQ1b v2/v7 并表。
- RQ1b 五门中 Behavior（C−B = −0.93pp）、Target、Search（有效率 −5.47pp）、Chain 均未通过；只有 Integrity 通过。
- ABC（C 臂）在 common-start 750 评测中未复现；Memory 内容研究 v2 批次零评测。
- 光学 T1 只可讲"达成 online 可行 Q=0.5552、独立 verifier 22/22"，不可讲相对基线提升或独立波前认证。
