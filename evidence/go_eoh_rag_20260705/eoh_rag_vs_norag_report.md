# InsertShips EOH · RAG vs 无 RAG(deepseek-v4-flash)

> 单元 = RC101–105 × 密度 × 到达缩放 t;RC103 d25/d50 因 SA 不收敛跳过 → 每臂 65 格。
> J_EOH 从每格 EOH 末代种群重过 guard 得到;guard:0<obj<1e9 且 obj≥ratio×J_SA。
> ΔJ=J_EOH−J_SA(负=EOH 优于 SA)。两臂同 guard,RAG vs 无RAG 的差值有效。

## guard ratio = 0.3

| 臂 | n | improved | tie | worse | no_valid | ΔJ 中位(有效) |
|---|---:|---:|---:|---:|---:|---:|
| 无 RAG | 65 | 26 | 8 | 28 | 3 | +0.00 |
| RAG | 65 | 21 | 8 | 33 | 3 | +131.51 |

**配对(同 65 格)**:RAG 更低 J = **17** / 无RAG 更低 = **23** / 平 = 20

| 密度 | 臂 | improved | tie | worse |
|---|---|---:|---:|---:|
| d25 | 无RAG | 11 | 1 | 8 |
| d25 | RAG | 10 | 0 | 10 |
| d50 | 无RAG | 7 | 0 | 12 |
| d50 | RAG | 8 | 0 | 12 |
| d75 | 无RAG | 8 | 7 | 8 |
| d75 | RAG | 3 | 8 | 11 |

## guard ratio = 0.5

| 臂 | n | improved | tie | worse | no_valid | ΔJ 中位(有效) |
|---|---:|---:|---:|---:|---:|---:|
| 无 RAG | 65 | 25 | 8 | 29 | 3 | +0.00 |
| RAG | 65 | 16 | 8 | 37 | 4 | +178.02 |

**配对(同 65 格)**:RAG 更低 J = **13** / 无RAG 更低 = **24** / 平 = 22

| 密度 | 臂 | improved | tie | worse |
|---|---|---:|---:|---:|
| d25 | 无RAG | 10 | 1 | 9 |
| d25 | RAG | 10 | 0 | 10 |
| d50 | 无RAG | 7 | 0 | 12 |
| d50 | RAG | 6 | 0 | 14 |
| d75 | 无RAG | 8 | 7 | 8 |
| d75 | RAG | 0 | 8 | 13 |

## 结论

- 在 Go InsertShips 轨上,RAG 相对无 RAG **无明显收益甚至略负**(最严 guard 0.5 下配对 RAG 赢 13 / 无RAG 赢 24)。与 Python 侧 RAG 的强正向效果相反。
- 无 RAG 的 EOH 本身与 SA 大致持平(improved≈worse),符合论文 16/11/16 的量级。
- ⚠ reps=1 有 run 间波动;d25 低密度存在 deep-cut(比值<0.5)刷分候选,已用 0.5 阈值做稳健性核对。
