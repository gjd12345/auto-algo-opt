"""Create a Kami review edition from a terminal online summary; retain historical evidence separately."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import statistics
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from audit_fme_pilot import audit

ROOT = Path(__file__).resolve().parents[1]
LABELS = {"bp_online": "在线装箱", "tsp_construct": "TSP", "cvrp_construct": "CVRP"}
ARMS = {"scalar": "标量", "passive": "被动分析", "active": "主动分析", "relevant": "相关历史",
        "shuffled": "随机历史", "transfer": "抽象提示", "shuffled_transfer": "随机抽象提示",
        "reference_scalar": "Pro 标量", "reference_active": "Pro 主动分析"}


def escape(value):
    return html.escape(str(value))


def percent(value):
    return "不可估计" if value is None else f"{value*100:+.2f}%"


def excerpt(value, maximum):
    clipped=value[:maximum]
    if len(value)>maximum and ' ' in clipped:
        clipped=clipped.rsplit(' ',1)[0]
    return escape(clipped)+'…'


def table(headers, rows):
    return "<table><thead><tr>" + "".join(f"<th>{escape(h)}</th>" for h in headers) + "</tr></thead><tbody>" + "".join(
        "<tr>" + "".join(f"<td>{escape(v)}</td>" for v in row) + "</tr>" for row in rows) + "</tbody></table>"


def headline_rows(summary, protocol):
    primary_contrasts=[('RQ1','scalar','active','主动分析 / 标量'),
                       ('RQ2','active','relevant','相关历史 / 无历史'),
                       ('RQ3','active','transfer','抽象提示 / 无提示'),
                       ('RQ4','active','reference_active','Pro / Flash · 主动分析')]
    rows=[]
    for rq,left,right,label in primary_contrasts:
        matching={row['problem']:row for row in summary.get('rq_results',{}).get(rq,{}).get('contrasts',[])
                  if row['control']==left and row['treatment']==right}
        if summary.get('scientific_claim_allowed') and all(matching.get(problem,{}).get('effect_claim_allowed') for problem in protocol['problems']):
            description='；'.join(f"{LABELS[problem]} {percent(matching[problem]['median_heldout_gain'])}" for problem in protocol['problems'])
        else:
            description='尚无满足完整性门禁的配对结果'
        rows.append([rq,label,description])
    return rows


def build(summary, protocol):
    cells = summary.get("cells", [])
    allowed = summary.get("scientific_claim_allowed", False)
    completed = sum(c["status"] == "completed" for c in cells)
    attempts = sum(c["candidate_attempts"] for c in cells)
    valid = sum(c["valid_candidates"] for c in cells)
    cost = summary.get('request_accounting', {})
    review = summary.get('result_review', {})
    status = "完整在线 pilot 已完成，结果仅具探索性" if allowed else "在线对照尚未完整，不能更新研究效果结论"
    historical = table(["问题", "历史结论（保留原口径）"], [
        ["RQ1", "机制记录改善，但有效候选率下降，质量门未通过"],
        ["RQ2", "TSP +0.83%、CVRP +5.95%，仅方向性支持"],
        ["RQ3", "迁移效果不确定，配对不完整"],
        ["RQ4", "旧 Model Router 在线实验未完成，返回 403"]])
    parts = [f'''<section class="cover"><div><div class="cover-eyebrow">FME · 在线实验审阅版</div>
    <div class="cover-title">分析是否带来<br>可复用的算法改进？</div>
    <div class="cover-sub">RQ1-RQ4 · OpenCode Go · DeepSeek V4 Flash / Pro<br>历史结论与新增在线证据分开呈现</div></div>
    <div class="cover-meta">agent_ad · Refactor0830<br>2026-08-31 · 人审 / 对外沟通</div></section>
    <section class="chapter" id="summary"><div class="chapter-num">01 · 结论</div><h1>{status}</h1>
    <p>研究主线只有一条：把算法分析变成可在评测前冻结、在评测后核对的预测，并检验它是否改善后续算法搜索。历史文献、进化记录和模型差异是同一主线上的实验变量，不另起框架。</p>
    {historical}<h2>本轮新增证据</h2>
    <p>协议计划 {summary.get('expected_cells', 81)} 个坐标，已返回 {len(cells)} 个坐标，其中完成或按预注册规则停止 {completed} 个。已返回坐标累计 {attempts} 次候选尝试、{valid} 个有效候选。该运行目录共记录 {cost.get('requests',0)} 次请求，其中 {cost.get('failed_requests',0)} 次失败；包含中断坐标和预检，但不包含独立诊断。</p>
    {table(['问题','本轮主对照','保留集配对中位改善'],headline_rows(summary,protocol))}
    <p>状态：{escape(summary['status'])}。以上仅为三 seed 探索性结果，旧质量门不直接移用；随机历史对照与模型交互见正文。预检或单次诊断成功不构成算法增益。</p>
    <p>{escape('本轮未建立主动控制的稳定额外收益。被动分析相对标量反馈在 TSP、CVRP 上有小幅方向性信号，值得作为最小主线继续研究；历史注入、主动反例和模型规模保留为可选消融。' if review else '阅读顺序：先核对对照，再查看配对效果、分析案例与证据边界。')}</p></section>''']
    controller_names={'scalar':'仅目标值反馈','passive':'分析与问题栈回流','active':'增加反例与主张复核'}
    history_names={'no_history':'无','relevant_history':'相关历史结果','shuffled_history':'随机历史结果',
        'abstract_transfer':'跨问题抽象提示','shuffled_abstract_transfer':'随机抽象提示'}
    matrix = [[ARMS[a['id']], controller_names[a['controller']], history_names[a['history']],
               protocol['resolved_models'][a['model_slot']].replace('deepseek-v4-','').capitalize()] for a in protocol['arms']]
    parts.append(f'''<section class="chapter" id="protocol"><div class="chapter-num">02 · 对照协议</div>
    <h1>预算一致，失败不补抽，结果不跨问题混算</h1>
    <p>3 个问题、3 个随机种子、9 个实验臂构成 81 个坐标。每坐标计划 {protocol['candidate_attempts']} 次候选尝试，生成失败和分析格式失败同样占用预算。这个次数是工程 pilot 选择，没有“8 次或 12 次最优”的文献依据，也不是统计功效保证。</p>{table(['实验臂','控制策略','历史输入','模型'],matrix)}
    <p>所有臂都生成评测前分析；标量组仅保存而不向后续生成提供，被动组复用分析和问题栈，主动组还执行开发反例与主张复核。预注册连续四次停滞可提前停止，保留最终算法和未用预算，曲线延伸为常数。实际 API 次数、token 和耗时另记，不能把预算上限当作等成本。</p>
    <p>仅未交付完整响应的传输故障最多重试 {protocol.get('network_retries',0)} 次，两模型参数一致，每次 HTTP 都记账；完整但低质量或无效的算法不重试。请求已消耗但供应商未返回用量的成本保持未知，不能算作零。</p>
    <p>每个 seed 冻结独立的开发训练、开发探测和最终保留集。先冻结全部坐标的最终算法哈希，才解封保留集。主张中的 supported 只表示开发改善方向相符，不等于因果机制得到验证。</p>
    <p>新合成数据中，装箱目标为使用箱数，TSP/CVRP 为路线长度。它们不能与历史 gap 常量混算。EOH 只负责提示与代码提取，检索只提供冻结证据，科研动作由同一个 FME 控制器类决定。</p></section>''')
    for number, rqs, title in [(3, ('RQ1','RQ2'), '分析与历史输入的收益分别检验'), (4, ('RQ3','RQ4'), '抽象提示与模型差异不等同于泛化')]:
        rows = []
        for rq in rqs:
            for row in summary.get('rq_results', {}).get(rq, {}).get('contrasts', []):
                auc=statistics.median(p['quality_auc_delta'] for p in row['pairs']) if row['pairs'] and not row['missing_seeds'] else None
                rows.append([rq, LABELS[row['problem']], f"{ARMS[row['control']]} → {ARMS[row['treatment']]}",
                    len(row['pairs']), f'{auc*100:+.2f}' if auc is not None else '不可估计', percent(row.get('median_heldout_gain')),
                    '探索性' if row['effect_claim_allowed'] else '不可归因'])
        content = table(['RQ','问题','对照 → 处理','配对','面积差¹','保留集改善','边界'],rows) if rows else '<p>本轮没有满足完整性门禁的可比较结果，不填补数值，也不从单坐标外推。</p>'
        if number==4:
            interaction_rows=[]
            for problem in protocol['problems']:
                group=[r for r in summary.get('rq_results',{}).get('RQ4',{}).get('interactions',[]) if r['problem']==problem]
                if len(group)==len(protocol['seeds']):
                    interaction_rows.append([LABELS[problem],len(group),
                        f"{statistics.median(r['controller_by_model_auc_interaction'] for r in group)*100:+.2f}",
                        f"{statistics.median(r['heldout_relative_gain_interaction'] for r in group)*100:+.2f}"])
            if interaction_rows:
                content+='<p>模型 × 主动控制的配对中位交互（面积 / 保留集，百分点）：' + '；'.join(
                    f'{row[0]} {row[2]} / {row[3]}' for row in interaction_rows) + '。各 seed 明细保留在机读结果中，不以中位数掩盖方向不一致。</p>'
        interpretation = ''.join(f'<p>{escape(review[rq])}</p>' for rq in rqs if rq in review)
        if number == 4 and review:
            overlap = review['random_abstract_itemset_overlap_pairs']
            interpretation += '<p>随机抽象对照与相关抽象提示选中相同条目集合的配对：' + '、'.join(
                f"{LABELS[problem]} {overlap[problem]}/{overlap['pairs_per_problem']}" for problem in protocol['problems']) + '。因此不能将整个对照差异归因于提示相关性。</p>'
        parts.append(f'''<section class="chapter"><div class="chapter-num">0{number} · 配对结果</div><h1>{title}</h1>
        <p>正值表示处理组更好。每一行先比较同一问题、同一 seed 的两个实验臂，再汇总配对中位数。¹ 面积是预算范围内的平均改善率，差值以百分点计；模型交互为 Pro 的主动控制增益减去 Flash 的增益。3 个 seed 只用于探索，不提供显著性或稳定泛化保证。</p>{content}
        <h2>本轮判断</h2>{interpretation or '<p>仅报告完整配对；失败保留，不从单坐标外推。</p>'}</section>''')
    metrics = []
    references = {row['cell_id']:row for row in summary['evidence_audit'].get('prediction_reference_checks',[])}
    for problem in protocol['problems']:
        for arm in ('scalar','passive','active','reference_scalar','reference_active'):
            group = [c for c in cells if c['problem']==problem and c['arm']['id']==arm]
            if not group:
                continue
            n=sum(c['candidate_attempts'] for c in group)
            v=sum(c['valid_candidates'] for c in group)
            analyzed=[c['analysis_metrics'] for c in group if c.get('analysis_metrics')]
            count=sum(m['count'] for m in analyzed)
            weighted=lambda field: sum(m[field]*m['count'] for m in analyzed)/count if count else None
            direction=weighted('direction_accuracy')
            brier=weighted('brier_score')
            positive=sum(references[c['cell_id']]['positive_outcomes'] for c in group)
            no_gain_accuracy=1-positive/count if count else None
            metrics.append([LABELS[problem],ARMS[arm],f'{v}/{n}',count,
                f'{direction:.1%}' if direction is not None else '不可估计',
                f'{no_gain_accuracy:.1%}' if no_gain_accuracy is not None else '不可估计',
                f'{brier:.3f}' if brier is not None else '不可估计'])
    parts.append(f'''<section class="chapter"><div class="chapter-num">05 · 分析潜力</div><h1>分析先预测，再接受核对</h1>
    <p>每个候选的分析、预期改善幅度和成功概率先写入追加式哈希账本并落盘，再运行候选评测。算法质量使用随候选预算变化的阶梯曲线；最后一次生成的收益不能提前计入前面的面积。</p>
    {table(['问题','实验臂','有效/尝试','分析数','方向正确','全猜无增益','Brier'],metrics) if metrics else '<p>当前没有可核对的前瞻分析样本。接口或格式诊断不计入本表。</p>'}
    <p>Brier 衡量概率预测偏差，越低越好。“全猜无增益”检查类别不平衡造成的虚高；恒定概率 0.5 的 Brier 为 0.25。两项只作事后描述参照，不修改预注册质量门。秩相关和 top-k 命中率见机读结果，样本或预测变化不足时不估计相关性。</p>
    <p>以上仅覆盖分析与算法评测均有效的样本，须结合有效率阅读。预测准确不证明因果作用；只有其回流能改善搜索，才支持主线能力。增加文字、档案或主张数量本身不是成功。</p>
    {('<p>全矩阵 ' + str(review['prediction_diagnostic']['matched_samples']) + ' 个可匹配有效样本中仅 ' + str(review['prediction_diagnostic']['positive_actual_outcomes']) + ' 个改善；模型方向准确率 ' + format(review['prediction_diagnostic']['direction_accuracy'], '.1%') + '，全猜无改善为 ' + format(review['prediction_diagnostic']['always_no_improvement_accuracy'], '.1%') + '。此合并数字只描述类别不平衡，不用于跨问题效果推断。</p>') if review else ''}</section>''')
    case_blocks=[]
    for case in summary['evidence_audit'].get('analysis_review_cases',[]):
        case_review=review.get('case_reviews',{}).get(case['analysis_id'])
        if case_review and case_review['candidate_id'] != case['candidate_id']:
            raise ValueError('Curated case does not match audited candidate')
        case_text=(f"<p>代码核对：{escape(case_review['code_grounded_review'])}</p><p>证伪核对：{escape(case_review['falsification_review'])}</p>" if case_review else
                   f"<p>机制原文节选：{excerpt(case['mechanism_excerpt'],200)}</p><p>最小证伪原文节选：{excerpt(case['falsification_excerpt'],140)}</p>")
        case_blocks.append(f'''<h2>{escape(LABELS[case['problem']])} · {escape(case['cell_id'])}</h2>
        <p>评测前预测 {percent(case['predicted_effect'])}，实际开发集相对父算法改善 {percent(case['actual_dev_train_effect'])}，预测成功概率 {case['predicted_success_probability']:.0%}。分析编号：{escape(case['analysis_id'])}。</p>
        {case_text}''')
    parts.append(f'''<section class="chapter"><div class="chapter-num">06 · 分析案例</div><h1>机制说得通，还要预测得准</h1>
    <p>每个问题选取一个有效候选中预测误差最大的案例，供人审查分析与实现是否对应。这是事后诊断，不代表平均水平，不是新增成功门槛；原始全文留在本地账本。</p>
    {''.join(case_blocks) if case_blocks else '<p>没有满足条件的候选案例。</p>'}
    <div class="takeaway"><div class="takeaway-label">主线如何收敛</div>先研究分析能否识别代码的真实排序与约束行为，形成可校准的预测，再检验其被动回流是否改善同预算搜索。不要把解释更长、档案更多当作算法潜力。</div></section>''')
    parts.append(f'''<section class="chapter"><div class="chapter-num">07 · 复现与限制</div><h1>保留失败，定位每个结论的证据</h1>
    <p>本版研究 ID：{escape(protocol['study_id'])}。协议哈希为下方 64 位摘要。源码、历史输入和数据划分均绑定该协议；旧运行不迁移进新坐标。</p><pre>{escape(protocol['protocol_hash'])}</pre>
    <h2>运行边界</h2><p>真实运行目录含请求成本、前瞻分析、候选评测、三类档案和动作记录。原始候选与大日志仅保存在本地忽略目录；Git 保存配置、精简结果和本报告，绝不保存 API key。</p>
    <p>协议落盘到结果落盘的观测时长约 {cost.get('artifact_span_seconds',0)/60:.1f} 分钟，来源为本机文件时间，非单调计时。已知输入 / 输出用量为 {cost.get('known_input_tokens',0):,} / {cost.get('known_output_tokens',0):,} token，另有 {cost.get('missing_usage_requests',0)} 次请求用量未知；不据此猜测费用。并发请求耗时之和不是实际运行时长。</p>
    <p>评测器使用独立进程、超时和数值接口检查，但不是操作系统安全沙箱。仅适用于本项目受限候选，不可用来执行不受信任的任意程序。</p>
    <h2>中断与更新原则</h2><p>Zen 返回 401，Go 的两个模型均通过简短预检。早期运行暴露超时、代码说明缺失和分析字段不明确；v6 共记录 423 次请求，其中一次连接重置，17/81 坐标返回后停止，保留集未解封。失败批次独立保留，v7 事先登记有限传输重试后全量重启，不拼接旧结果。</p>
    <p>证据审计状态：{escape(summary['evidence_audit']['status'])}。账本哈希、分析先于评测、反例准入、保留集顺序和配对结果均从原始记录复核；这只证明证据一致性，不证明效果显著。</p>
    <p>同模型重跑不保证逐 token 复现；本报告支持协议、数据和证据链复核，不把随机生成伪装成确定性计算。模型比较仅覆盖本次请求的非思考设置及供应商实际返回的模型标识。</p>
    <h2>直接来源</h2><ul><li>历史表：refactor0830_phase4/rq1_rq4_offline_replay.json。</li>
    <li>本轮：随报告提供的 online_review.json 与本地冻结协议。</li>
    <li><a href="https://opencode.ai/docs/go/">OpenCode Go 官方接口说明</a>，核对于 2026-08-31。</li>
    <li><a href="https://api-docs.deepseek.com/guides/thinking_mode/">DeepSeek 思考模式参数</a>，核对于 2026-08-31。</li></ul>
    <p>Phase 6 的多领域扩展暂不推进，先完成 RQ1-RQ4 的质量、有效性与证据完整性复核。</p></section>''')
    return '\n'.join(parts)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    summary_path=args.run_dir/'summary.json'
    summary=json.loads(summary_path.read_text(encoding='utf-8'))
    protocol=json.loads((args.run_dir/'protocol_frozen.json').read_text(encoding='utf-8'))
    summary['evidence_audit']=audit(args.run_dir.resolve())
    review_path=ROOT/'agent_records/calibrations/refactor0830_v7_result_review_20260831.json'
    if protocol['study_id'] == 'refactor0830_opencode_go_pilot_v7':
        review=json.loads(review_path.read_text(encoding='utf-8'))
        if review['raw_summary_sha256'] != hashlib.sha256(summary_path.read_bytes()).hexdigest():
            raise ValueError('Curated review requires the exact audited raw summary')
        summary['result_review']=review
    requests=[]
    for journal in args.run_dir.rglob('events.jsonl'):
        for line in journal.read_text(encoding='utf-8').splitlines():
            event=json.loads(line)
            if event['kind']=='model_request': requests.append(event['payload'])
    summary['request_accounting']={'requests':len(requests),
        'failed_requests':sum(not row['ok'] for row in requests),
        'known_input_tokens':sum(row.get('input_tokens') or 0 for row in requests),
        'known_output_tokens':sum(row.get('output_tokens') or 0 for row in requests),
        'missing_usage_requests':sum(row.get('input_tokens') is None or row.get('output_tokens') is None for row in requests),
        'summed_request_seconds_not_wall_time':sum(row.get('elapsed_seconds') or 0 for row in requests),
        'by_requested_model':{model:{
            'requests':sum(row['model']==model for row in requests),
            'failed_requests':sum(row['model']==model and not row['ok'] for row in requests),
            'successful_retry_requests':sum(row['model']==model and row['ok'] and row.get('transport_attempt',1)>1 for row in requests),
            'known_input_tokens':sum(row.get('input_tokens') or 0 for row in requests if row['model']==model),
            'known_output_tokens':sum(row.get('output_tokens') or 0 for row in requests if row['model']==model),
            'successful_response_model_ids':sorted({str(row.get('response_model')) for row in requests if row['model']==model and row['ok']})
        } for model in sorted({row['model'] for row in requests})}}
    artifact_start=(args.run_dir/'protocol_frozen.json').stat().st_mtime
    artifact_end=summary_path.stat().st_mtime
    summary['request_accounting'].update({
        'artifact_span_seconds':max(0,artifact_end-artifact_start),
        'protocol_written_utc':datetime.fromtimestamp(artifact_start,timezone.utc).isoformat(),
        'summary_written_utc':datetime.fromtimestamp(artifact_end,timezone.utc).isoformat(),
        'wall_time_boundary':'Observed local file timestamp span, not monotonic process timing; copying or rewriting raw files invalidates this estimate'})
    template=(ROOT/'eoh_rag_workspace/reports/refactor0830_phase5/refactor0830_fme_rq_report.html').read_text(encoding='utf-8')
    content=template[:template.index('<body>')]+'<body>'+build(summary,protocol)+'</body></html>'
    content=content.replace('<title>FME 单一科研主线：重构与 RQ1–RQ4 验证</title>','<title>FME RQ1-RQ4 在线实验审阅报告</title>')
    content=content.replace('FME 单一科研主线、RQ1-RQ4 离线重放与在线模型阻塞报告','FME 在线对照、前瞻分析潜力与证据边界')
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'online_review.html').write_text(content,encoding='utf-8')
    compact={key:value for key,value in summary.items() if key!='cells'}
    compact['raw_summary_sha256']=hashlib.sha256(summary_path.read_bytes()).hexdigest()
    compact['cells']=[{key:value for key,value in cell.items() if key not in {'usage','archives'}} for cell in summary.get('cells',[])]
    (args.output/'online_review.json').write_text(json.dumps(compact,ensure_ascii=False,indent=2),encoding='utf-8')
    tree=ET.parse(ROOT/'eoh_rag_workspace/reports/refactor0830_phase5/fme_mainline_architecture.drawio')
    labels={'2':'FME：前瞻分析驱动的算法研究','3':'同一控制器 · 冻结对照 · 开发证据回流；held-out 仅用于最后报告',
        '11':'冻结协议\n3 问题 × 3 seed × 9 实验臂','12':'评测前冻结分析\n数值预测 · 风险 · 最小证伪',
        '34':'OpenCode Go\nDeepSeek V4 Flash / Pro','42':'真实档案准入\n行为 · 接纳反例 · 主张状态',
        '43':'最终保留集\n所有最终算法冻结后解封','51':'RQ1-RQ4 配对\n无历史 / 随机历史 / 模型对照',
        '52':'质量与分析两条评价轴\n预算曲线 · 方向预测 · 概率校准',
        '53':'审阅报告\n效果 · 失败 · 不确定性'}
    graph=tree.find('.//root')
    for cell in graph.findall('mxCell'):
        if cell.get('id') in labels: cell.set('value',labels[cell.get('id')])
        if cell.get('id')=='74': graph.remove(cell)
    edge=ET.SubElement(graph,'mxCell',id='75',value='仅开发证据回流',edge='1',parent='1',source='42',target='21',
        style='edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;dashed=1;exitX=0.5;exitY=1;entryX=0;entryY=0.5;strokeColor=#1B365D;')
    geometry=ET.SubElement(edge,'mxGeometry',relative='1',attrib={'as':'geometry'})
    points=ET.SubElement(geometry,'Array',attrib={'as':'points'})
    ET.SubElement(points,'mxPoint',x='760',y='910')
    ET.SubElement(points,'mxPoint',x='20',y='910')
    ET.SubElement(points,'mxPoint',x='20',y='390')
    tree.write(args.output/'online_architecture.drawio',encoding='utf-8',xml_declaration=True)
    print(json.dumps({'status':summary['status'],'report_html':str(args.output/'online_review.html')}))


if __name__=='__main__':
    main()
