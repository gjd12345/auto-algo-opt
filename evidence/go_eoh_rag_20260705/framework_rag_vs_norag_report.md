# 框架 RAG(retriever)vs 无 RAG · InsertShips 小批量(deepseek-v4-flash)

> 26 格代表子集(3 密度 × t{1.0,0.6} × 全部有效实例)。RAG 用**框架检索**(`build_official_rag_context('insertships_go','literature_rag',top_k=5)`,
> 静态检索全部 5 张插入策略卡 + API 骨架,4000 字,存 `framework_ctx_insertships.txt`)。无 RAG 臂取自全量网格同格结果。

## 结果

| 臂 | improved | tie | worse | ΔJ 中位 |
|---|---:|---:|---:|---:|
| 框架 RAG | 1 | 4 | 21 | +235.7 |
| 无 RAG(同格) | 16 | 3 | 7 | ~0 |

**配对(同 26 格,框架RAG vs 无RAG):框架RAG 更低 J = 0 / 无RAG 更低 = 18 / 平 = 8**

## 结论

- **框架静态 RAG(全塞 5 卡)重伤 EOH-Go**:21/26 格比 SA 差,配对**从未赢过无 RAG**(0 胜),ΔJ 中位 +235.7。
- 三者排序:**无 RAG(最好)> 手写 v1(略伤,见 eoh_rag_vs_norag_report.md)> 框架 5 卡静态检索(重伤)**。
- 规律:**RAG 上下文越多,EOH-Go 越差** —— 大段策略卡把 deepseek-v4-flash 带向更复杂更差的 InsertShips;不给上下文反而写得简单又好。
- ⚠ reps=1(但 21/26 worse + 配对 0 胜 18 负远超噪声);top_k=5 **全塞、未上 reranker**。唯一可能救回 RAG 的变体 = reranker 只选 1–2 张卡(少而精),尚未测。
