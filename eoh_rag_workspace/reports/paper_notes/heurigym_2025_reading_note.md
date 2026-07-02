# HeuriGym 论文阅读笔记

## 基本信息

- **标题**: HeuriGym: An Agentic Benchmark for LLM-Crafted Heuristics in Combinatorial Optimization
- **作者**: Hongzheng Chen 等 (Cornell, Harvard, NVIDIA)
- **发表**: ICLR 2026 (arXiv: 2506.07972)

---

## 一、核心问题

当前 LLM 评测存在两大缺陷：(1) 基于标准答案的评测（AIME、HumanEval）已饱和且易被记忆污染；(2) 基于裁判偏好的评测（Chatbot Arena）高方差、不一致。HeuriGym 主张：CO 问题是评测 LLM 的理想场景——明确定义的目标函数、巨大解空间、抗记忆性（NP-hard 难穷举）。

---

## 二、评测框架

**Agentic loop 架构**，三阶段：

| 阶段 | 检查内容 |
|------|----------|
| Stage I: Execution | 程序能否正确编译/执行 |
| Stage II: Solution Generation | 能否在超时内产生非空输出 |
| Stage III: Verification | 解是否满足所有约束（verifier 检查） |

每个问题配有 Verifier + Evaluator + 反馈循环。

---

## 三、指标体系

### SOLVEs@i（通过率）
```
SOLVEs@i := (1/N) * Σ 1(pass stage s in first i iterations)
```

### QUALITY（质量）
```
QUALITY = (1/N̂) * Σ min(1, c*_n / c_n)
```
c_n = LLM 解代价，c*_n = 专家解代价，N̂ = 通过验证的实例数。

### YIELD（产出率）
```
YIELD = N̂ / N
```

### QYI（质量-产出综合指数）— 核心指标
```
QYI = Quality × Yield
```
专家基线 QYI = 1.0。

---

## 四、问题集（9 个 CO 问题）

| 领域 | 问题 | 难度 |
|------|------|------|
| EDA | Operator scheduling | ★ |
| EDA | Technology mapping | ★★ |
| EDA | Global routing | ★★★ |
| 编译器 | E-graph extraction | ★ |
| 编译器 | Intra-operator parallelism | ★★ |
| 计算生物学 | Protein sequence design | ★ |
| 计算生物学 | Mendelian error detection | ★★ |
| 物流 | Airline crew pairing | ★★ |
| 物流 | Pickup and delivery w/ time windows | ★★ |

**选择标准**：文献曝光度低（最高引用 <1000）、明确自然语言规范、巨大解空间（某些 >10^65,000）、可扩展实例。**故意排除 TSP/SAT** 防记忆污染。

---

## 五、实验结果

| 模型 | SOLVE^III @1 | SOLVE^III @10 | QYI |
|------|-------------|---------------|-----|
| GPT-o4-mini-high | 53.2% | 74.8% | ~0.60 |
| DeepSeek-R1 | 44.0% | 73.4% | — |
| Gemini-2.5-Pro | 20.2% | 65.1% | **0.62** |
| Claude-3.7-Sonnet | 9.2% | 60.1% | — |
| 专家基线 | — | — | 1.00 |

进化框架对比：
| 框架 | SOLVE^III @10 | QYI |
|------|---------------|-----|
| Gemini-2.5-Pro (单模型) | 0.6514 | **0.6170** |
| EoH | 0.4954 | 0.4492 |
| ReEvo | 0.4771 | 0.4486 |

**关键发现**：单模型 > 进化框架（在 HeuriGym 上）；迭代优化至关重要；Quality-Yield 权衡是根本挑战。

---

## 六、对 TOCC 的启示

- QYI 指标值得借鉴：同时考虑可行性和质量
- 三阶段验证（执行→解生成→约束验证）与 TOCC 的 gatekeeper 对齐
- 单模型 > 进化框架的发现提示：进化框架的价值可能在于 search steering 而非 raw quality
- TOCC 的 card selection 可以看作一种轻量级的 hyper-heuristic 选择

---

*阅读日期: 2026-06-09*
