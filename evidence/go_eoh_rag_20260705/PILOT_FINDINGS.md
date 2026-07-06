# EOH-Go J_EOH 臂 · pilot 发现与模型选择(2026-07-05)

## 目的
论文 Guarded EOH-Go 的 J_EOH 臂:每格跑一轮 EOH 进化(gen=1, pop=4,种子=贪心 InsertShips),
guard 过滤后最优候选 = J_EOH,与 SA 基线 J_SA 比得 ΔJ。两臂:RAG(注入 insertships_v1.txt)/ 无 RAG。

## 关键发现:模型决定 J_EOH 可信度
目标函数 `final cost` 只算距离、不罚车辆数,存在被"多开车/丢单"刷低分的空子。同一无 RAG 设置、
同一 guard(0.3×J_SA + 静态查丢单模式)下,不同模型行为差异极大:

| 单元 | J_SA | JoyAI-LLM-Pro | deepseek-v4-flash | 归档(dsv4) |
|---|---|---|---|---|
| RC101 d25 t1.0 | 664.1 | **211(−68%,刷分)** | 570.6(−14%)/ 664(tie) | 657 |
| RC101 d75 t1.0 | 549.5 | **220(−60%,刷分)** | 376.7(−31%) | 549(tie) |
| RC102 d50 t1.0 | 551.8 | 422.95 | 422.95(一致) | — |
| RC104 d50 t1.0 | 376.2 | 316.6 | 314.1(一致) | — |

- **JoyAI-LLM-Pro 会钻空子**:造出 211/220 这类刷分候选,且 ratio 0.318 刚好过 0.3 线,论文 guard 拦不住。
- **deepseek-v4-flash 不明显钻空子**:改进幅度合理(14–31%),与 JoyAI 在诚实格子上一致;偶发刷分候选被
  guard 拦下(RC101 d25 susp=1)。→ **deepseek-v4-flash + 论文原 guard = 可信,无需额外硬校验器**。
- deepseek-v4-flash 带 reasoning,约 **350s/格**;65 格 × 两臂 ≈ 12h。
- reps=1 有 run 间波动(同格 570 vs 664),**聚合 improved/tie/worse 计数**比单格 ΔJ 更稳。

## 结论
用 **deepseek-v4-flash**(论文原模型,opencode Go 端点)跑两臂 × 65 格;guard 用论文原版即可。
RC103 d25/d50 无 J_SA 锚点(SA 病态)自动跳过 → 每臂 65 格。

## 复现
```bash
cd Agent_EOH/eoh/src/eoh/examples/user_insertships_go
export DEEPSEEK_API_KEY=... DEEPSEEK_API_ENDPOINT=https://opencode.ai/zen/go/v1/chat/completions DEEPSEEK_MODEL=deepseek-v4-flash
python3 run_insertships_eoh_grid.py --output-dir <out>/norag --sa-baseline <sa_summary.csv>          # 无 RAG 臂
python3 run_insertships_eoh_grid.py --output-dir <out>/rag   --sa-baseline <sa_summary.csv> --rag    # RAG 臂
```
