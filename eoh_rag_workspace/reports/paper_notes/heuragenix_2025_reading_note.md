# HeurAgenix 论文阅读笔记

## 基本信息

- **标题**: HeurAgenix: Leveraging LLMs for Solving Complex Combinatorial Optimization Challenges
- **作者**: Xianliang Yang 等 (Microsoft)
- **发表**: 2025年6月 (arXiv: 2506.15196)
- **代码**: https://github.com/microsoft/HeurAgenix

---

## 一、核心思想

两阶段超启发式框架：**(1) 启发式进化** + **(2) 动态启发式选择**。

---

## 二、阶段一：启发式进化

### 种子来源（三种）
1. LLM 直接生成
2. 从研究论文 LaTeX 中提取
3. 从相关问题迁移适配

### 进化机制
1. **扰动**：对种子引入多样化策略变异（比例 0.1，最大 1000 次）
2. **LLM 精炼**：对比种子解与更高质量解，提取可复用进化策略（每轮 5 次精炼，top-1 过滤）
3. **多轮迭代**：默认 3 次进化循环
4. **问题状态反馈**：用详细问题状态描述理解启发式表现

统一函数签名：
```python
def heuristic_name(problem_state: dict, algorithm_data: dict, **kwargs) -> tuple[Operator, dict]
```

---

## 三、阶段二：动态启发式选择

| 策略 | 描述 |
|------|------|
| 直接应用 | 单一固定启发式 |
| LLM 超启发式 | LLM 运行时从目录中选择（每 5 步一次） |
| 随机超启发式 | 从池中随机选择 |
| MCTS (TTS) | rollout-based 评估 |

### 双奖励机制 + GRPO 微调
- **选择偏好信号**：学习在给定状态下哪个启发式更优
- **状态感知信号**：学习理解问题状态特征
- 用 GRPO（Group Relative Policy Optimization）微调轻量级选择器
- 架构解耦：重计算（进化，大 LLM）vs 轻选择（微调小模型）

---

## 四、四阶段流水线

```
问题状态生成 → 基础启发式生成 → 启发式进化 → 启发式选择/求解
```

---

## 五、与 TOCC 的关键差异

| 维度 | HeurAgenix | TOCC |
|------|-----------|------|
| 启发式来源 | LLM 自动生成和进化 | 预定义策略卡 |
| 选择对象 | 可执行启发式代码 | 短指令卡（<=450 chars） |
| 选择条件 | 问题状态特征 | 执行轨迹（trace） |
| 是否生成新策略 | 是（核心能力） | 否（仅从已有库选择） |
| 训练复杂度 | 高（需 RL 微调） | 低（检索匹配） |
| 推理开销 | 需运行进化循环 | 仅检索+选择 |
| 适用场景 | 需要发现新启发式 | 有成熟策略库 |

---

## 六、对 TOCC 的启示

- HeurAgenix 的"问题状态"概念与 TOCC 的"trace"概念类似，但抽象层次不同
- 双奖励机制的思想可以借鉴：TOCC 的 card selection 也可以学习"哪种 trace 配哪种 card"
- HeurAgenix 的进化 + 选择是重路径；TOCC 是轻路径（不生成代码，只注入知识）
- 两者不竞争，可以组合：TOCC cards 作为 HeurAgenix 种子启发式的知识增强

---

*阅读日期: 2026-06-09*
