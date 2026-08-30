#!/usr/bin/env python3
"""Build the Refactor0830 human-review report from the frozen Kami template."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def pct(value: float, digits: int = 2) -> str:
    return f"{value * 100:.{digits}f}%"


def build_body(evidence: dict[str, object]) -> str:
    rq1 = evidence["RQ1"]
    rq2 = evidence["RQ2"]
    rq3 = evidence["RQ3"]
    rq4 = evidence["RQ4"]
    curves = evidence["quality_potential_curves"]

    tsp_gain = pct(rq2["tsp_construct"]["relative_improvement_outcome_vs_pure"])
    cvrp_gain = pct(rq2["cvrp_construct"]["relative_improvement_outcome_vs_pure"])
    control_valid = pct(rq1["control_valid_candidate_rate"], 1)
    fme_valid = pct(rq1["fme_valid_candidate_rate"], 1)
    pairs = rq3["complete_pairs_by_problem"]
    wtl = "/".join(str(item) for item in rq3["win_tie_loss"])

    curve_rows = []
    labels = {"bp_online": "BP-online", "tsp_construct": "TSP", "cvrp_construct": "CVRP"}
    for problem in ("bp_online", "tsp_construct", "cvrp_construct"):
        item = curves[problem]
        curve_rows.append(
            "<tr>"
            f"<td>{labels[problem]}</td>"
            f"<td>{item['completed_runs']}</td>"
            f"<td>{item['quality_auc']:.3f}</td>"
            f"<td>{item['first_run_budget_reaching_5pct']}</td>"
            f"<td>{pct(item['final_best_normalized_improvement'], 2)}</td>"
            "</tr>"
        )

    return f"""
<section class="cover">
  <div>
    <div class="cover-eyebrow">科研重构报告 · HUMAN REVIEW EDITION</div>
    <div class="cover-title">FME 单一科研主线<br>重构与 RQ1–RQ4 验证</div>
    <div class="cover-sub">Refactor0830 · 从分散探索路线收敛到可证伪的多问题算法研究闭环</div>
  </div>
  <div class="cover-meta">
    <strong>agent_ad · Refactor0830</strong><br>
    V1.0 · 2026-08-30<br>
    人审 / 对外沟通版
  </div>
</section>

<section class="toc">
  <h2>目录</h2>
  <div class="toc-item"><span class="toc-num">01</span><a class="toc-title" href="#summary">执行摘要</a></div>
  <div class="toc-item"><span class="toc-num">02</span><a class="toc-title" href="#mainline">收敛后的完整主线</a></div>
  <div class="toc-item"><span class="toc-num">03</span><a class="toc-title" href="#design">研究问题与评价协议</a></div>
  <div class="toc-item"><span class="toc-num">04</span><a class="toc-title" href="#results">RQ1–RQ4 证据结果</a></div>
  <div class="toc-item"><span class="toc-num">05</span><a class="toc-title" href="#potential">算法潜力，而不只是末次得分</a></div>
  <div class="toc-item"><span class="toc-num">06</span><a class="toc-title" href="#router">模型配置与在线阻塞</a></div>
  <div class="toc-item"><span class="toc-num">07</span><a class="toc-title" href="#decision">结论、边界与下一步</a></div>
  <div class="toc-item"><span class="toc-num">A</span><a class="toc-title" href="#appendix">复现索引与参考文献</a></div>
</section>

<section class="chapter" id="summary">
  <div class="chapter-num">01 · Executive Summary</div>
  <h1>执行摘要</h1>
  <p class="lead">本轮重构已经把活跃科研面收敛为一条主线：<span class="hl">FME 是唯一科学控制器</span>，EOH 负责候选生成，RAG / 历史库负责受边界约束的证据冷启动，BP、TSP、CVRP 由统一问题适配器接入。已有证据足以否定若干过强假设，但尚不足以宣称在线跨模型收益。</p>
  <div class="exec-summary">
    <h2>给评审者的四句话</h2>
    <ol>
      <li><strong>主线已收敛：</strong>不再把 EOH、RAG、TOCC、router、selector 各自当成独立科研路线；它们只在能改善反馈、记忆、泛化、质量或复现时作为适配器存在。</li>
      <li><strong>RQ1 出现负证据：</strong>历史 BP 配对证据中，FME 机制记录更完整，但有效候选率从 {control_valid} 降至 {fme_valid}，不能宣称质量提升。</li>
      <li><strong>RQ2 有问题依赖的方向性信号：</strong>结果感知历史检索相对纯检索在 TSP 与 CVRP 的中位改进分别为 {tsp_gain} 与 {cvrp_gain}；历史数据缺少 shuffled control，因此只能作方向性结论。</li>
      <li><strong>RQ4 在线实验被外部权限阻塞：</strong>Model Router 连接与鉴权路径可达，但 DeepSeek V4 Flash 预检返回 HTTP 403（模型符号不存在或账号无权限）；报告不会把历史异协议 cohort 拼成跨模型因果结论。</li>
    </ol>
  </div>
  <div class="takeaway"><div class="takeaway-label">Decision</div>继续投入的是“可证伪的算法研究闭环”，不是更多并列框架。下一笔模型预算应在同一冻结协议下补齐 prospective analysis 与 cross-model cohort，而不是延长任意固定的 8 代。</div>
</section>

<section class="chapter" id="mainline">
  <div class="chapter-num">02 · Converged Mainline</div>
  <h1>收敛后的完整主线</h1>
  <p class="lead">一个控制器、三类适配器、两条潜力曲线、一道 held-out 边界，构成完整且可审计的研究叙事。</p>
  <figure>
    <img src="fme_mainline_architecture.png" alt="FME 单一科研主线架构图">
    <figcaption>图 1：Refactor0830 的活跃科研面。红色虚线代表严格边界或当前外部阻塞。</figcaption>
  </figure>
  <h2>保留什么，为什么保留</h2>
  <table>
    <thead><tr><th>组成</th><th>在主线中的唯一职责</th><th>保留门槛</th></tr></thead>
    <tbody>
      <tr><td>FME Research Loop</td><td>统一问题栈、动作选择、证据更新、反例与决策</td><td>必须形成可证伪 claim 与证据边界</td></tr>
      <tr><td>EOH</td><td>候选算法生成、变异与反思提示</td><td>只作为 CandidateGeneratorAdapter</td></tr>
      <tr><td>RAG / 历史库</td><td>注入相关文献、历史进化、失败经验与抽象迁移证据</td><td>有冻结快照、引用哈希、held-out 隔离</td></tr>
      <tr><td>ProblemAdapter</td><td>把 BP-online、TSP、CVRP 变成可比的生成—评估接口</td><td>统一预算单位与 cohort 口径</td></tr>
      <tr><td>模型 Provider</td><td>可替换的算法生成 / 分析模型</td><td>同协议比较，不能混用历史 cohort</td></tr>
    </tbody>
  </table>
  <div class="callout">EOH 和 RAG 仍然需要，但不再“统治主线”。EOH 回答“如何产生候选”，RAG 回答“允许给候选生成器看什么”；科学问题、可比性与是否继续由 FME 决定。</div>
</section>

<section class="chapter" id="design">
  <div class="chapter-num">03 · Research Design</div>
  <h1>研究问题与评价协议</h1>
  <p class="lead">研究对象不是“某个提示能否偶然跑高分”，而是系统是否更快、更稳、更可解释地发现具有算法潜力的机制。</p>
  <table>
    <thead><tr><th>RQ</th><th>核心对比</th><th>主要指标</th><th>本轮证据类型</th></tr></thead>
    <tbody>
      <tr><td>RQ1</td><td>标量反馈 vs 结构化被动分析 vs FME 主动反思</td><td>质量、有效候选率、反例与机制 claim</td><td>冻结历史配对重放</td></tr>
      <tr><td>RQ2</td><td>无历史 vs 相关历史 vs shuffled history</td><td>相对改进、达到阈值预算、污染检查</td><td>历史消融；缺 shuffled arm</td></tr>
      <tr><td>RQ3</td><td>无迁移 vs 仅抽象机制迁移</td><td>跨问题 win/tie/loss、稳定性</td><td>不完整配对重放</td></tr>
      <tr><td>RQ4</td><td>Controller × Model 的冻结 2×2 比较</td><td>模型主效应、控制器主效应、交互效应</td><td>历史单模型 + 在线预检</td></tr>
    </tbody>
  </table>
  <h2>为什么不是固定 8 次算法生成</h2>
  <p>未找到支持“8 次 / 8 代具有普适最优性”的文献依据。EoH 报告的典型设置约为 20 代与约 2,000 次 LLM 查询；ReEvo 使用 30 个初始候选与 100 次评估预算；FunSearch、EPS 等工作也使用随任务变化的预算。由此，本项目把 8 代降级为历史工程设置，正式口径改为：</p>
  <div class="takeaway"><div class="takeaway-label">Budget Rule</div>横轴统一使用可核对的候选评估数或模型调用数；报告完整的 anytime curve、阈值到达预算与 normalized AUC。达到预算、证据饱和或失败退出条件任一项即停，而不是为了凑固定代数继续生成。</div>
</section>

<section class="chapter" id="results">
  <div class="chapter-num">04 · Evidence Results</div>
  <h1>RQ1–RQ4：结果与能说到哪里</h1>
  <table>
    <thead><tr><th>RQ</th><th>冻结结果</th><th>判定</th><th>允许的结论</th></tr></thead>
    <tbody>
      <tr><td>RQ1</td><td>3 个配对 seed；control/FME 有效候选率 {control_valid}/{fme_valid}；3 条开发 claim、4 个承认反例</td><td><span class="tag">质量门未过</span></td><td>机制记录更完整，但当前实现降低有效候选率；应先修生成约束</td></tr>
      <tr><td>RQ2</td><td>TSP {tsp_gain}；CVRP {cvrp_gain}；各 3 seed</td><td><span class="tag">方向性支持</span></td><td>结果感知检索可能有帮助，且高度问题依赖；不能排除检索量或关键词效应</td></tr>
      <tr><td>RQ3</td><td>完整配对：BP {pairs['bp_online']}、TSP {pairs['tsp_construct']}、CVRP {pairs['cvrp_construct']}；win/tie/loss = {wtl}</td><td><span class="tag">不确定</span></td><td>抽象迁移尚无稳定增益；缺 TSP 配对，不能宣布泛化成功</td></tr>
      <tr><td>RQ4</td><td>DeepSeek 历史 605 runs；在线预检 403；历史 JoyAI 与 DeepSeek 协议不同</td><td><span class="tag">在线阻塞</span></td><td>可报告 DeepSeek 历史曲线；不可报告跨模型因果效果</td></tr>
    </tbody>
  </table>
  <h2>这组结果最重要的价值</h2>
  <p>第一，它证明“分析更丰富”与“算法更好”是两个必须分开的评价轴。RQ1 的机制门通过而质量门失败，正是需要保留的负结果。第二，RQ2 暗示历史注入不是全局开关，而是问题—证据匹配函数。第三，RQ3 暴露迁移研究最容易犯的错误：在配对不完整时把局部 win 写成泛化。</p>
  <blockquote>收敛不是删到只剩一条漂亮故事，而是把每条支线变成主线上的可替换部件，并给它明确的失败退出条件。<span class="cite">— Refactor0830 研究口径</span></blockquote>
</section>

<section class="chapter" id="potential">
  <div class="chapter-num">05 · Algorithm Potential</div>
  <h1>不只看末次进化：看算法潜力</h1>
  <p class="lead">最终 best score 只能回答“是否找到过好候选”；潜力曲线进一步回答“多早找到、是否持续改善、分析是否能预测后续增益”。</p>
  <h2>质量潜力曲线</h2>
  <p>对最小化问题，以初始基线 J₀ 和预算 b 内最优值 J*(b) 定义 Q(b) = (J₀ − J*(b)) / max(|J₀|, ε)，并在统一预算区间计算 normalized AUC。</p>
  <table>
    <thead><tr><th>问题</th><th>历史 runs</th><th>质量 AUC</th><th>首次达到 5% 的 run</th><th>最终最优改进</th></tr></thead>
    <tbody>{''.join(curve_rows)}</tbody>
  </table>
  <p>BP 的高 AUC 来自很早发现并保持大幅改进；TSP/CVRP 的最终改进接近，但 CVRP 到达 5% 阈值更慢。这种差异在只看最终 best 时会消失。</p>
  <h2>分析潜力曲线</h2>
  <p>历史资产未在看到结果前冻结“预测效果与置信度”，因此本轮不能诚实估计分析潜力。新实现的 <code>AnalysisRecord</code> 已要求在评估前记录 observation、hypothesis、predicted effect、probability、regime、risk、cheapest falsification 与 evidence hash。下一 cohort 才能计算：</p>
  <ul>
    <li>方向准确率、Spearman 相关与 top-k hit：分析能否排序潜力候选；</li>
    <li>Brier score / calibration：置信度是否可信；</li>
    <li>counterexample decision value：分析是否能及时停止无效路线；</li>
    <li>analysis-to-gain efficiency：单位分析成本换来的真实质量增益。</li>
  </ul>
  <div class="callout">本轮明确把“无法估计”写入结果，而不是从已经看到 outcome 的事后文本反推分析准确率。这是防止自证循环的关键边界。</div>
</section>

<section class="chapter" id="router">
  <div class="chapter-num">06 · Model Router</div>
  <h1>模型配置正确，在线权限尚未满足</h1>
  <p class="lead">随附 PDF 明确了 OpenAI Chat Completions 兼容协议；本地配置已完成且密钥仅保存在 Git 忽略的 <code>.env</code> 中。</p>
  <table>
    <thead><tr><th>配置项</th><th>值 / 状态</th></tr></thead>
    <tbody>
      <tr><td>Endpoint</td><td><code>https://model-router.edu-aliyun.com/v1/chat/completions</code></td></tr>
      <tr><td>Authorization</td><td><code>Bearer &lt;MODEL_ROUTER_API_KEY&gt;</code>；真实值不进入报告与 Git</td></tr>
      <tr><td>模型标识规则</td><td>PDF 要求精确的 <code>symbol/model_code</code></td></tr>
      <tr><td>当前推定标识</td><td><code>deepseek/deepseek-v4-flash</code>；需以账号模型广场实际 symbol 为准</td></tr>
      <tr><td>预检结果</td><td>HTTP {rq4['model_router_preflight']['http_status']} · {html.escape(rq4['model_router_preflight']['error_summary'])}</td></tr>
    </tbody>
  </table>
  <h2>阻塞如何解释</h2>
  <p>原始短名 <code>deepseek-v4-flash</code> 会被网关拒绝为格式错误，说明请求已到达 Model Router。改为若干 <code>symbol/model_code</code> 候选后返回 403，且 PDF 示例模型在当前账号下同样返回 403；<code>GET /v1/models</code> 不可用。证据更符合“账号尚未授权或真实 marketplace symbol 未知”，而不是本地 provider 代码错误。</p>
  <div class="takeaway"><div class="takeaway-label">解除阻塞的最小动作</div>在 Model Router 模型广场为该 API key 开通 DeepSeek V4 Flash，并复制页面显示的完整 <code>symbol/model_code</code>；只需更新本地 <code>MODEL_ROUTER_MODEL</code> 后重跑 preflight 与冻结 2×2 manifest。无需再次重构代码。</div>
</section>

<section class="chapter" id="decision">
  <div class="chapter-num">07 · Decision & Next Steps</div>
  <h1>结论、证据边界与下一步</h1>
  <h2>截至本版的完成状态</h2>
  <table>
    <thead><tr><th>Phase</th><th>交付</th><th>状态</th></tr></thead>
    <tbody>
      <tr><td>1</td><td>分支、Provider、.env.example、执行契约、脱敏预检证据</td><td>完成</td></tr>
      <tr><td>2</td><td>FME 单主线、EOH/RAG 适配器、三问题注册表、去活跃支线</td><td>完成</td></tr>
      <tr><td>3</td><td>问题栈、前瞻分析、冻结冷启动、双潜力指标</td><td>完成</td></tr>
      <tr><td>4</td><td>RQ1–RQ4 冻结历史重放与结果资产</td><td>离线完成；RQ4 在线 cohort 被 403 阻塞</td></tr>
      <tr><td>5</td><td>人审报告、PDF、Draw.io 源图与预览</td><td>完成</td></tr>
    </tbody>
  </table>
  <h2>下一轮只做三件事</h2>
  <ol>
    <li><strong>先修 RQ1 的有效候选率：</strong>把结构化分析用于生成约束与最小证伪，而不是仅增加反思文本长度；退出条件是有效候选率仍显著低于 control。</li>
    <li><strong>补齐 RQ2/RQ3 的关键对照：</strong>加入 shuffled history 与 TSP 抽象迁移完整配对；不增加新框架。</li>
    <li><strong>权限开通后一次性跑 RQ4：</strong>冻结 Controller × Model 的 2×2 manifest，统一问题、seed、候选评估预算与温度，报告主效应和交互效应。</li>
  </ol>
  <div class="takeaway"><div class="takeaway-label">Stop Rule</div>任何方向若不能转化为更好的反馈、记忆、泛化、质量或复现能力，或在最小验证预算内未改善潜力曲线，就退出活跃主线并转为历史资产。</div>
</section>

<section class="chapter" id="appendix">
  <div class="chapter-num">A · Reproducibility</div>
  <h1>复现索引与参考文献</h1>
  <h2>A.1 关键资产</h2>
  <ul>
    <li><code>agent_records/contracts/refactor0830_execution_contract_v1.json</code>：本轮执行边界。</li>
    <li><code>eoh_rag/fme/mainline.py</code>：收敛后的运行时组合。</li>
    <li><code>eoh_rag/fme/analysis.py</code>、<code>cold_start.py</code>、<code>potential.py</code>：问题栈、冷启动与潜力指标。</li>
    <li><code>eoh_rag_workspace/experiments/manifests/refactor0830_rq1_rq4_offline_replay_v1.json</code>：重放 manifest。</li>
    <li><code>eoh_rag_workspace/reports/refactor0830_phase4/rq1_rq4_offline_replay.json</code>：机器可读结果。</li>
    <li><code>agent_records/calibrations/model_router_deepseek_v4_flash_preflight_20260830.json</code>：脱敏 API 预检证据。</li>
  </ul>
  <h2>A.2 文献</h2>
  <ol>
    <li>EoH: <a href="https://arxiv.org/abs/2401.02051">Evolution of Heuristics</a>.</li>
    <li>ReEvo: <a href="https://arxiv.org/abs/2402.01145">Reflective Evolution of Heuristics</a>.</li>
    <li>FunSearch: <a href="https://www.nature.com/articles/s41586-023-06924-6">Mathematical discoveries from program search with large language models</a>.</li>
    <li>EPS: <a href="https://arxiv.org/abs/2407.10873">Evolutionary Program Synthesis with LLMs</a>.</li>
    <li>Self-Refine: <a href="https://arxiv.org/abs/2303.17651">Iterative Refinement with Self-Feedback</a>.</li>
    <li>Reflexion: <a href="https://arxiv.org/abs/2303.11366">Language Agents with Verbal Reinforcement Learning</a>.</li>
    <li>LLaMEA: <a href="https://arxiv.org/abs/2405.20132">A Large Language Model Evolutionary Algorithm</a>.</li>
    <li>AlphaEvolve: <a href="https://arxiv.org/abs/2506.13131">A coding agent for scientific and algorithmic discovery</a>.</li>
  </ol>
  <h2>A.3 审阅提示</h2>
  <p>本报告不包含 API key、原始模型响应、缓存或不可比较的跨 cohort 拼接。所有百分比来自冻结 JSON；“方向性支持”“不确定”“在线阻塞”均为正式结论的一部分，而非待隐藏的异常。</p>
</section>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    template = args.template.read_text(encoding="utf-8")
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    body = build_body(evidence)

    body_start = template.index("<body>")
    body_end = template.index("</body>") + len("</body>")
    report = template[:body_start] + "<body>\n" + body + "\n</body>" + template[body_end:]
    report = report.replace("<title>{{文档标题}}</title>", "<title>FME 单一科研主线：重构与 RQ1–RQ4 验证</title>")
    report = report.replace("{{文档标题}}", "FME 单一科研主线")
    report = report.replace('<meta name="author" content="{{作者}}">', '<meta name="author" content="agent_ad · Refactor0830">')
    report = report.replace('<meta name="description" content="{{摘要}}">', '<meta name="description" content="FME 单一科研主线、RQ1-RQ4 离线重放与在线模型阻塞报告">')
    report = report.replace('<meta name="keywords" content="{{关键词}}">', '<meta name="keywords" content="FME, EOH, RAG, algorithm discovery, RQ1-RQ4">')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
