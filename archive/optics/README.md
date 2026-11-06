# archive/optics —— 光学处方优化线的归档材料

光学设计（T1/T3 透镜、`artifact_session`、`optics_backend`）曾是与本仓库并行的**第二条运行时**，现已整体退出主干。
代码不属于主研究线，但实验证据与接口文档保留在本目录，避免"删代码 = 删证据"。

## 删除了什么

在 `integration/thesis-core` 上：

```powershell
git rm -r extensions          # 45 个已跟踪文件：artifact_session(14 模块) + optics_backend(7 模块) + reports/skills/tests/tools
```

同时删除 CI 的 `optics` job、`README.md` 的光学路线与快速开始、`docs/README.md` 与 `reports/README.md` 的光学入口，并清理 `.gitattributes` 中指向该目录的规则。

## 保留了什么

| 路径 | 说明 |
| --- | --- |
| `docs/optics_multibackend_trd.md` | 多后端技术需求文档（37KB，原 `docs/`） |
| `docs/optics_multibackend_implementation_plan.md` | 实施方案（14KB，原 `docs/`） |
| `reports/p0_p5_acceptance_20260917.md` | P0–P5 验收记录（基线 `8a37fdda`） |
| `reports/p1_acceptance_20260917.md` | P1 阶段验收 |
| `optics_evolution_process_review_20260918.md` | 进化过程复盘（原在未跟踪工作区） |
| `preexisting-working-tree.patch` | 删除前工作区里那 3 处未提交改动（7,438 字节），来源 `git diff archive/skill-runtime snapshot-2026-11-06-wt -- extensions/optics` |

## 恢复完整代码

```powershell
git checkout archive/six-mirror -- extensions
```

`archive/six-mirror` = `723c5ef3`（`codex/optics-backend-v1`），其 8 个提交包含六镜牛顿法的决策合同、`optics_optim` 采样构造、coarse Newton 基线、曲率关闭梯度种子与环境钉版。

> 注意：`six_mirror` 只存在于该分支，`27442cb7`（本主干的起点）里没有——因此在主干上不需要改动 `agent_skill_loop/evaluator.py` 的 problem registry。

## 引用时的事实边界

- 唯一一次真实在线 T1：9 轮、170 次生成（去重后仅 66 种处方）、最终 online 可行 **Q = 0.5552282993353802**、用掉 **195/500** 物理评测（171 online 含 baseline + 20 audit + 4 verifier）、5 份四档 audit 全 PASS、独立 verifier 22/22 PASS（reward=1）、第 9 轮由 Agent 主动停止。
- **不能讲"相对基线提升"**：同 run 基线 Q = 0.2640065476546554 但**不可行**，不构成同可行域比较。
- **不能讲"独立波前认证"**：验证是几何光线追迹/OTF proxy，`independent_wavefront_verified=false`；22/22 只针对最终处方。
- **不能讲"已跨域泛化"**：`artifact_session` 与 `agent_skill_loop` 双向 import 数为 0，唯一接缝是 evaluator 的 problem registry；跨域是"共享设计模式"，不是共享实现。
- **T3 仅离线**：只有资产身份与 online/四档 audit 的原入口差分，无 live 优化、无 T3 的 Q 或轮数。
- Windows only；Linux 3.12.14 未验证（WSL 启动失败 `HCS_E_SERVICE_NOT_AVAILABLE`，Docker 不可用）。
- 原始 `.local/` 证据不在 git 中，只发布了去密摘要。
