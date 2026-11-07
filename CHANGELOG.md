## v1.2.2 —— 2026-11-07 · benchmark 注册表修复版

主题：修掉 `island605_bp` 档位"注册即不可用"的问题，并把「registry 声明哈希 = 磁盘字节哈希」做成 CI 门。

### Fixed

- **`island605_bp` 的 manifest 哈希是草稿值**：`benchmarks/eohs_v1/registry.json` 声明的 `train_hash=f900b345…`、`test_hash=1fe78d40…`、`reference_hash=1d171a0f…` 与已提交文件的实际字节哈希（`7101b734…` / `13c7edd6…` / `c3e87a55…`）全部不符，且从引入提交 `d876c791` 起就不符（8 种规范化序列化都复现不出旧值，属陈旧哈希）。后果是 `catalog.load_profile_suite()` 在字节校验处直接抛 `data_manifest_hash_mismatch`，该档位对任何走 registry 的调用方都不可达——605 当年是绕过 registry 直接调 problem 模块才跑通的。
- **哈希链同步重算**：`metric_spec.reference_manifest_hash` 同样携带旧值，改动它会使 `MetricSpec.content_hash` 变化，因此 `metric_spec_hash` 一并从 `fd1c3f2f…` 更新为 `9a30d2ec…`。

### Changed（证据身份，必须注意）

- `island605_bp` 的 `benchmark_spec_hash` / `metric_spec_hash` 与 v1.2.1 及更早版本不同。凡此前记录过该档位身份值的地方，都应按本版重算；其余三个 `eohs_v1` 档位未受影响（哈希本来就对）。

### Added

- `tests/kernel/test_benchmark_registry_hashes.py`（9 条）：每个档位声明的 train/test/reference 哈希必须等于磁盘字节；`metric_spec_hash` 必须等于 `MetricSpec(**metric_spec).content_hash`；metric 的 reference hash 必须等于 `manifests.reference_hash`；四档都能 `load_profile_suite(dev_train)`；`island605_bp` 的 `test` split 必须抛 `heldout_locked_no_access`；baseline 目标 `0.03984304255961364` 与 5 条实例向量固定。

### Verified（本地，Windows · Python 3.11.9）

- `pytest tests/kernel tests/knowledge` → **264 passed, 2 skipped**。
- `island605_bp` 经 registry 载入后 baseline = `0.039843042560`，与绕过 registry 的实测值逐位一致。

## v1.2.1 —— 2026-11-06 · 发布门修复版

主题：修掉 v1.2.0 在远程 CI 上的两处发布门失败。v1.2.0 的 tag 保留在 `c98b184`（CI 红），本版只做最小修复，不改变研究结论。

### Fixed

- **wheel 外部安装不再要求官方 EoH**：`eoh_frozen/identity.py` 的 `loaded_identity()` 把 `import eoh` 改为可选；未安装 extra 时 `upstream` 报 `{"status": "not_installed", "commit": null}`，不再抛 `ModuleNotFoundError`。`agent_skill_loop/session_supervisor.py` 的 `run_startup_preflight()` 新增 `require_eoh` 开关：真实 Session 仍要求官方 EoH（缺包必失败），只有 `tools/verify_release_install.py` 的 wheel 身份检查传 `require_eoh=False`。
- **compact evidence 补齐轮级边车**：`tools/export_benchmark_evidence.py` 现在按 `evaluation_facts` 里的描述符导出 `rounds/round_NNNN/execution_delta.json`、`comparison_packet.json`，并按 `finish-round` receipt 导出 `memory_consumption.json`；同时新增 `cost_summary.json`（`outer_controller.status = "unavailable"`、`total_model_tokens = null`、`total_model_token_status = "incomplete"`），明确"宿主 Agent 的 token 不在 Runtime 可观测范围内"，避免 R05 式的静默低报。这同时关闭了独立评审 R08 的"导出未含 execution_delta/memory_consumption"部分。

### Verified（本地，Windows · Python 3.11.9）

- `pytest tests/kernel tests/knowledge` → **255 passed, 2 skipped**。
- `EOH_REQUIRED=1 pytest tests/eoh_frozen`（已装官方 EoH `47254578`）→ **45 passed**。
- `python tools/verify_release_install.py`（干净的 3.11 venv：只有 numpy、无 eoh）→ `{"wheel_install": "passed", ...}`。
- **未验证**：Linux runner；远程 CI 见本提交触发的 run。
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

- `extensions/optics/`（45 个已跟踪文件，另 2 份设计文档迁入归档）及其 CI、测试、依赖与文档入口；六镜牛顿（`six_mirror_*`）随之退出主干（它的代码只存在于 tag `archive/six-mirror`）。
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
