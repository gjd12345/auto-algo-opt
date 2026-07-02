# 有公开代码的 LLM-CO / AHD 工作源码调研

日期：2026-06-09  
范围：只纳入有公开代码或作者公开仓库的组合优化 LLM agent / AHD 工作。  
目标：读论文相关仓库源码，判断它们对 TOCC 的架构、指标、tool-use 和论文定位有什么直接启发。  
执行约束：不安装依赖、不跑训练、不读取或打印任何 API key；只做源码结构阅读。

---

## 1. 本轮纳入 / 排除规则

### 纳入标准

```text
1. 论文或项目页明确给出 GitHub / official code。
2. 仓库当前可访问，或至少 GitHub 页面能公开读取结构。
3. 与 LLM + combinatorial optimization + heuristic/program search 相关。
```

### 排除标准

```text
1. 只有论文，没有公开代码。
2. 论文声称有代码，但仓库当前 404 或不可 clone。
3. 只有二手解读，没有作者仓库。
```

---

## 2. 源码获取状态

| 工作 | 公开代码 | 本地状态 | 本轮源码阅读深度 | 结论 |
|---|---|---|---|---|
| CO-Bench | https://github.com/sunnweiwei/CO-Bench | clone 成功 | 读 README、agent abstraction、EoH wrapper、evaluator | 纳入 |
| HeuriGym | https://github.com/cornell-zhang/heurigym | clone 成功 | 读 LLM solver agent、executor、feedback、metric | 纳入 |
| HeurAgenix | https://github.com/microsoft/HeurAgenix | clone 成功 | 读 README、generator、evolver、LLM selector、function-to-tool | 纳入 |
| EoH-S | https://github.com/FeiLiu36/EoH-S | clone 卡住 early EOF；GitHub 页面可读 | 读 README / repo structure / run entry 描述 | 暂纳入公开代码列表，但源码深读未完成 |
| ReEvo | https://github.com/ai4co/reevo | clone 卡住 early EOF；GitHub 页面可读 | 读 README / repo structure / method scope | 暂纳入公开代码列表，但源码深读未完成 |
| EoH | https://github.com/FeiLiu36/EoH | clone 卡住 early EOF；GitHub 页面可读 | 读 GitHub 页面确认公开仓库 | 暂纳入公开代码列表，但源码深读未完成 |
| CoupleEvo | 论文给出 https://github.com/tb-git-kit-research/CoupleEvo | clone 返回 repository not found | 未读源码 | 暂不纳入源码结论 |
| CoEvo-AHD | 未找到公开官方代码 | 无 | 未读源码 | 暂不纳入源码结论 |

本地克隆路径：

```text
eoh_rag_workspace/external_repos/CO-Bench
eoh_rag_workspace/external_repos/heurigym
eoh_rag_workspace/external_repos/HeurAgenix
```

---

## 3. CO-Bench 源码阅读

### 3.1 结构事实

关键文件：

```text
CO-Bench/README.md
CO-Bench/agents/base.py
CO-Bench/agents/eoh_agent.py
CO-Bench/agents/funsearch.py
CO-Bench/agents/reevo.py
CO-Bench/evaluation/evaluate.py
CO-Bench/evaluation/utils.py
```

README 明确给出 agent 抽象：

```text
step()     -> 返回下一段 candidate code
feedback() -> 接收上一段 code 的 evaluation result
finalize() -> 返回最终 code
```

评价 loop 是：

```text
for it in range(64):
    code = agent.step()
    feedback = evaluator.evaluate(code)
    agent.feedback(feedback.dev_score, feedback.dev_feedback)
code = agent.finalize()
```

### 3.2 实现要点

`agents/eoh_agent.py` 做了一个 EoH 的 step-by-step wrapper：

- 用 `SimpleProblem` 和 `SimplePrompts` 包装任意 problem description。
- 初始阶段用 `i1` 生成个体。
- evolution 阶段依次用 `e1/e2/m1/m2` 等 operator。
- population management 按 objective 去重、保留最优。
- parent selection 用 rank-based probability。

`evaluation/evaluate.py` 把 generated solve function 和 eval function 分离：

- `evaluate_instance(instance, solve, eval_func)` 执行 candidate。
- `Evaluator.evaluate(code)` 并行跑 test cases。
- 输出 `score/dev_score/test_score` 和 `feedback/dev_feedback/test_feedback`。

### 3.3 对 TOCC 的启发

CO-Bench 对我们最重要的是 **统一 agent API 和 evaluation feedback**：

```text
agent.step -> evaluator.evaluate -> agent.feedback -> agent.finalize
```

TOCC 可以对齐这个抽象，但我们的差异是：

```text
CO-Bench agent 直接生成/改进 code。
TOCC controller 选择下一轮 operator-card prior，再交给 EOH 生成 code。
```

可写成论文边界：

```text
CO-Bench benchmarks LLM agents for algorithm search.
TOCC studies how to steer such algorithm search via trace-conditioned operator-card selection.
```

---

## 4. HeuriGym 源码阅读

### 4.1 结构事实

关键文件：

```text
heurigym/llm_solver_agent.py
heurigym/scripts/main.py
heurigym/scripts/feedback.py
heurigym/scripts/metric.py
heurigym/scripts/run.py
heurigym/*/README.md
```

问题目录包含 README + program template + verifier/evaluator 思路。`scripts/main.py` 只负责调用 LLM 写出的 `solver.solve(...)`。`scripts/feedback.py` 负责：

```text
verify(input_files, output_file)
if valid:
    evaluate(input_files, output_file)
else:
    cost = inf
```

`scripts/metric.py` 的归一化是：

```text
normalize_score = min(1, baseline / score)
```

### 4.2 实现要点

`llm_solver_agent.py` 的关键设计：

- `ProblemReader` 从每个 problem 的 README 中解析 problem description。
- `ProgramExecutor.save_program()` 从 LLM response 中抽取最长 code block，写入 iteration 目录。
- 每轮将 problem 的 program skeleton、run script、feedback script 复制到 iteration 目录。
- `execute_program()` 对 train data 执行生成代码，限制 timeout 和 CPU threads。
- 反馈来自 verifier/evaluator，而不是 LLM 自评。

### 4.3 对 TOCC 的启发

HeuriGym 直接支持我们把 success funnel 写成主指标，而不是只看 objective：

```text
validity / verification / execution / cost
```

它对 TOCC 的启发：

1. `generation_success` 应该是主指标。没有足够 valid candidates，objective 没统计意义。
2. verifier/evaluator 应该与 generated code 隔离，TOCC 不能让 LLM 自己判断有效。
3. 报告里应同时展示 yield/pass 和 quality。对应我们现在的：

```text
diagnosis_success
proposal_accept
linkage_success
generation_success
objective_success
```

---

## 5. HeurAgenix 源码阅读

### 5.1 结构事实

关键文件：

```text
HeurAgenix/README.md
HeurAgenix/src/pipeline/heuristic_generator.py
HeurAgenix/src/pipeline/heuristic_evolver.py
HeurAgenix/src/pipeline/hyper_heuristics/llm_selection.py
HeurAgenix/src/util/function_to_tool.py
HeurAgenix/launch_hyper_heuristic.py
```

问题目录：

```text
src/problems/tsp
src/problems/cvrp
src/problems/jssp
src/problems/mkp
src/problems/max_cut
src/problems/dposp
```

每个 problem 有统一结构：

```text
components.py
env.py
problem_state.py
prompt/problem_description.txt
prompt/problem_state.txt
heuristics/
```

统一 heuristic 函数签名：

```python
def heuristic_name(problem_state: dict, algorithm_data: dict, **kwargs) -> tuple[Operator, dict]:
```

### 5.2 HeuristicGenerator

`heuristic_generator.py` 支持三种来源：

```text
generate_from_llm
generate_from_paper
generate_from_reference
```

关键设计：

- background 中包含 problem description、env summary、components。
- 从 paper 生成时，先读 abstract 判断是否相关，再逐 section 找可实现的 heuristic。
- 从 reference problem 迁移时，会显式比较 source/target problem 的 component similarity。
- 生成后可用 `smoke_test()` 反复修复代码。

对 TOCC 的启发：

```text
文献卡不是直接塞全文，而应被转成可执行 skill/card。
跨问题迁移不是凭直觉选卡，应该显式记录 source problem -> target problem 的相似性。
```

### 5.3 HeuristicEvolver

`heuristic_evolver.py` 的核心是从正负轨迹中找 bottleneck：

```text
basic heuristic -> negative solution
perturbation heuristic -> positive solution
compare positive vs negative trajectory
LLM identify bottleneck operations
LLM raise suggestion
validate / refine
```

这和 TOCC 的 trace diagnosis 非常接近。区别是：

```text
HeurAgenix 诊断单个 solving trajectory 的 bottleneck operation。
TOCC 诊断一次 EOH run 的 search bias / card mismatch / valid collapse。
```

### 5.4 LLMSelectionHyperHeuristic

`llm_selection.py` 是最接近 TOCC 的部分：

- 读取 `heuristic_pool` 中每个 heuristic 的 docstring。
- 每 `selection_frequency` 步让 LLM 从 pool 中选 heuristic。
- 可选 tool calling：把 heuristic function 转为 OpenAI-style tool schema。
- 记录 trajectory：每次选择前后的 observation delta。
- 可用 `tts_bon()` 做 test-time scaling / best-of-n selection。

关键差异：

```text
HeurAgenix selects heuristics during a single solve trajectory.
TOCC selects operator cards before the next EOH run.
```

这非常重要。TOCC 不要写成“我们也做 heuristic selector”，而要写成：

```text
run-level context-selection controller for heuristic evolution
```

### 5.5 function_to_tool.py

`function_to_tool.py` 将 heuristic function 转成 tool schema：

- 用 AST 找函数定义。
- 解析 docstring 的 description 和 Args。
- 跳过 `problem_state / algorithm_data / args / kwargs`。
- 输出 OpenAI function-calling 格式。

这直接支持我们之前讨论的方向：

```text
把 local-search delta / candidate evaluation / card selector 等封装成工具，
让 LLM proposer 调用工具而不是重写底层循环。
```

但实现边界要不同：

```text
HeurAgenix tool = solving-time heuristic function.
TOCC tool = research workflow primitive.
```

### 5.6 源码风险观察

`launch_hyper_heuristic.py` 会把 `llm_config_file` 的内容写入 `parameters.txt`。如果配置文件中包含真实 key，可能导致 artifact 泄漏。

这反过来证明我们当前规则是必要的：

```text
API key 不读取、不打印、不 echo；
run artifact 不入 git；
配置只记录 PRESENT=true/false。
```

---

## 6. 公开仓库但本轮未完成源码深读

### 6.1 EoH-S

公开仓库： https://github.com/FeiLiu36/EoH-S  
状态：GitHub 页面可读；本地 clone 卡住并被中止。

已读到的公开信息：

- 基于 LLM4AD platform。
- 目标是 Automated Heuristic Set Design（AHSD）。
- 不再输出单个 heuristic，而是小规模互补 heuristic set。
- 代码结构包括：

```text
code/
datasets/
examples/
heuristics/
results/
```

对 TOCC 的意义：

```text
它支持“不同 instance / distribution 需要互补 heuristic/card”的论点。
TOCC 可以把 operator-card memory 解释成一种 run-level prior portfolio。
```

待做：

```text
单独下载 zip 或 sparse checkout code/ 目录；
深读 EoHS / EoHSProfiler / complementary population management。
```

### 6.2 ReEvo

公开仓库： https://github.com/ai4co/reevo  
状态：GitHub 页面可读；本地 clone 卡住并被中止。

已读到的公开信息：

- 目录包含：

```text
baselines/
cfg/
problems/
prompts/
utils/
main.py
reevo.py
```

- 支持 TSP、CVRP、OP、MKP、BPP、DPP。
- 支持 NCO、GA、ACO、GLS、constructive heuristics。

对 TOCC 的意义：

```text
ReEvo 的 reflective evolution 是 candidate-level feedback。
TOCC 的 trace diagnosis 是 run-level feedback。
```

待做：

```text
深读 reevo.py、prompts、problems/tsp/cvrp。
```

### 6.3 EoH

公开仓库： https://github.com/FeiLiu36/EoH  
状态：GitHub 页面可读；本地 clone 卡住并被中止。

对 TOCC 的意义：

```text
EoH 是 base engine。我们不需要把 EoH 写成贡献点，而应写 TOCC 如何控制 EoH 的 context/card prior。
```

待做：

```text
如果后续需要复核 EoH 原始 operator，实现可用 zip 或 sparse checkout。
```

---

## 7. 明确排除

### 7.1 CoupleEvo

论文和检索页给出的代码地址：

```text
https://github.com/tb-git-kit-research/CoupleEvo
```

本轮 clone 结果：

```text
remote: Repository not found.
fatal: repository ... not found
```

结论：当前不可作为“公开源码已读”证据，只能作为论文层相关工作。

### 7.2 CoEvo-AHD

本轮没有找到官方公开代码仓库。  
结论：暂不纳入源码调研，只保留为 primary-source reading 候选。

---

## 8. 对 TOCC 的直接架构建议

### 8.1 TOCC 应吸收的设计

| 来源 | 可吸收设计 | TOCC 落点 |
|---|---|---|
| CO-Bench | `step / feedback / finalize` agent API | 将 TOCC proposal loop 形式化为 observe -> propose -> validate -> run -> summarize |
| HeuriGym | verifier/evaluator 分离，yield/quality 双指标 | success funnel 中强化 generation_success 和 objective_success |
| HeurAgenix | problem_state + heuristic pool + LLM selector | card pool + trace state + LLM proposer |
| HeurAgenix | function-to-tool AST wrapper | 将 TraceReader/CardSelector/Gatekeeper/Summarizer 做成 tool schemas |
| HeurAgenix | positive/negative trajectory bottleneck diagnosis | 将 pure/default/tocc traces 做成 positive/negative run comparison |
| EoH-S | complementary heuristic set | card memory 不追求单卡全能，而追求 per-problem/per-distribution 互补 |

### 8.2 TOCC 不能照搬的设计

| 不能照搬 | 原因 |
|---|---|
| HeurAgenix 的 state-level heuristic selector | TOCC 不是求解过程中选 heuristic，而是下一轮 EOH 前选 cards |
| HeuriGym 的 full autonomous solver loop | TOCC 需要 gatekeeper 和 manifest 限制预算，不能让 LLM 自由控制 run |
| CO-Bench 的 agent framework 对比方式 | 我们短期没有能力覆盖 36 问题，应先做 TSP/CVRP/BP + 迁移 smoke |
| EoH-S 的 heuristic set objective | TOCC 不是直接输出 heuristic set，而是输出 operator-card subset |

---

## 9. 论文定位更新

建议 related work 写法：

```text
CO-Bench and HeuriGym evaluate LLM agents for algorithm/heuristic generation in CO.
EoH, ReEvo, and EoH-S improve the heuristic evolution process itself.
HeurAgenix studies dynamic heuristic selection during problem solving.
TOCC instead studies trace-conditioned selection of operator-card priors before the next heuristic-evolution run.
```

一句话区分：

```text
HeurAgenix chooses which heuristic to apply to the current solving state.
TOCC chooses which operator-card priors to inject into the next LLM-based evolution run.
```

---

## 10. 下一步源码深读计划

优先级：

1. **HeurAgenix 深读**  
   抽取 `LLMSelectionHyperHeuristic`、`function_to_tool`、trajectory logging 的伪代码，映射到 TOCC V2/V3。

2. **HeuriGym 深读**  
   抽取 execution / verification / cost pipeline，改造我们的 summary 报告为 quality-yield 双指标。

3. **CO-Bench 深读**  
   抽取 agent API 和 evaluation interface，决定 TOCC 是否要暴露 `step / feedback / finalize` 兼容层。

4. **EoH-S / ReEvo 单独拉取源码**  
   当前 clone 卡住；建议下次用 zip 或 sparse checkout，只拉 `code/`、`reevo.py`、`prompts/`、`problems/`。

---

## 11. 本轮命令记录

```bash
git clone --depth 1 https://github.com/sunnweiwei/CO-Bench.git
git clone --depth 1 https://github.com/cornell-zhang/heurigym.git
git clone --depth 1 https://github.com/microsoft/HeurAgenix.git
git clone --depth 1 https://github.com/FeiLiu36/EoH.git          # early EOF, stopped
git clone --depth 1 https://github.com/ai4co/reevo.git           # early EOF, stopped
git clone --depth 1 https://github.com/FeiLiu36/EoH-S.git        # early EOF, stopped
git clone --depth 1 https://github.com/tb-git-kit-research/CoupleEvo.git  # 404
```

---

## 12. Sources

- CO-Bench paper: https://arxiv.org/abs/2504.04310
- CO-Bench code: https://github.com/sunnweiwei/CO-Bench
- HeuriGym paper: https://arxiv.org/abs/2506.07972
- HeuriGym code: https://github.com/cornell-zhang/heurigym
- HeurAgenix paper: https://arxiv.org/abs/2506.15196
- HeurAgenix code: https://github.com/microsoft/HeurAgenix
- EoH-S code: https://github.com/FeiLiu36/EoH-S
- ReEvo code: https://github.com/ai4co/reevo
- EoH code: https://github.com/FeiLiu36/EoH
