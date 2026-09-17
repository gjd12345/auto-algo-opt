# T1 处方优化：Luna 外层实验摘要

日期：2026-09-17。框架提交：92a90bde8f249359984cf2d0d939c7458f699c4d。
外层 GPT-5.6-Luna（high），内层 qwen/deepseek-v4.1-flash；adapted_external_controller。
Windows Python3.12.11，不宣称 Linux3.12.14 原环境复现。

## 结果

- 9轮、170次候选生成，最终 online 可行 Q=0.5552282993353802。
- 本run基线 Q=0.2640065476546554，但不可行；不能把两者简单表述为同可行域的相对提升。
- Runtime 5份四档audit均PASS；最终处方独立verifier 22/22 PASS、reward=1。
- 实际物理profile=195/500上限：171online（含baseline）+20audit+4verifier。
- 终态 COMPLETED / agent_complete：第9轮由Agent主动停止，不是预算用尽。
- 170份候选仅66种不同处方，116份online可行；重复104次（61.2%）。
- Memory配置开启，但本run没有写入/消费条目，不能宣称Memory增益。
- provider输入546951、输出46604 tokens；外层完整token和货币成本不可观测。

| 轮次 | 搜索方向 | 请求Δ/累计 | online可行/生成 | incumbent Q |
|---|---|---:|---:|---:|
| 1 | 多变量恢复可行性 | 10/10 | 7/10 | 0.504204 |
| 2 | 孔径、曲率与焦面补偿 | 20/30 | 17/20 | 0.531764 |
| 3 | 固定厚度的细化搜索 | 20/50 | 19/20 | 0.531764 |
| 4 | 厚度驱动形状调整 | 20/70 | 5/20 | 0.531764 |
| 5 | 孔径—焦面二维搜索 | 20/90 | 19/20 | 0.533415 |
| 6 | 孔径边界探索 | 20/110 | 10/20 | 0.537966 |
| 7 | 曲率对与焦面协调 | 20/130 | 12/20 | 0.555228 |
| 8 | 曲率与焦面微调 | 20/150 | 14/20 | 0.555228 |
| 9 | 厚度扰动及补偿 | 20/170 | 13/20 | 0.555228 |

## 证据边界

只读复核1472条事件链、176份完整assessment，hash一致；复核无模型/物理调用。
原始run ID：t1_luna_20260917_500_session；私有证据位于原光学worktree的
`extensions/optics/.local/`。本文件只发布去密摘要，不移动/改写冻结证据。
verifier目录：verifier_logs_t1_luna_20260917_500；verification SHA256：
7ec25d83d518958a7887ccf1277029d1fa141c0cb6de8d23f4be3a211cc54bd2。

independent_wavefront_verified=false：验证为几何光线追迹/OTF proxy，不是独立波前认证。
单run结果不证明统计显著性、Luna相对其他控制器优势或已找到最优。
原手写round_progress遗漏第9轮且误用EoH/invalid标签，第1/7轮可行数也分别误记6/10；
本表直接按online_facts重计为7/12（总计116），并补齐第9轮，
不修改原运行证据。下一步优先研究重复控制、停滞后的机制多样性及停止策略。
