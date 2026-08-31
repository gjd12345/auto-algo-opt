"""Build a bounded RQ1b evidence projection and canonical portable-report input.

Reads an already completed run and its audit. Never calls a model or solver.
Raw responses, candidate programs, credentials and large journals stay local.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import sqlite3
from statistics import mean, median
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eoh_rag.fme.online_adapters import digest, file_hash
from eoh_rag.fme.behavior_analysis import metrics

ARMS = ('scalar', 'passive', 'behavior_grounded')
LABELS = dict(zip(ARMS, ('A · Scalar', 'B · Passive', 'C · Grounded')))


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def events(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def interval(values, statistic=median):
    """Post-run descriptive paired bootstrap; seeds, never individual probe rows."""
    rng = random.Random(83031)
    draws = sorted(statistic(rng.choices(values, k=len(values))) for _ in range(10000))
    return [draws[249], draws[9749]]


def pct(value):
    return '不可计算' if value is None else f'{100*value:+.2f}%'


def pp(value):
    return '不可计算' if value is None else f'{100*value:+.2f} pp'


def project(run, audit):
    summary, protocol = read(run/'summary.json'), read(run/'protocol_frozen.json')
    if summary['status'] != 'pilot_completed' or audit.get('status') != 'evidence_integrity_verified':
        raise ValueError('report_requires_completed_online_run_and_successful_audit')
    cells = summary['cells']
    by_arm = {arm: [c for c in cells if c['arm']['id'] == arm] for arm in ARMS}
    rows_by_arm = {arm: {'behavior': [], 'targeted': []} for arm in ARMS}
    failures, parse_errors, cases = Counter(), Counter(), []
    for c in cells:
        arm = c['arm']['id']
        stream = events(run/'cells'/c['cell_id']/'events.jsonl')
        analyses = {e['payload']['analysis_id']: e['payload'] for e in stream if e['kind'] == 'prospective_analysis'}
        for e in stream:
            p = e['payload']
            if e['kind'] == 'prospective_analysis':
                for err in p['forecast']['errors']:
                    parse_errors[f'{arm}/{err.split(":")[0]}'] += 1
            if e['kind'] not in {'candidate_evaluation', 'candidate_attempt_failure'}:
                continue
            for name in rows_by_arm[arm]:
                rows_by_arm[arm][name].extend(p['measurement_rows'][name])
            if e['kind'] == 'candidate_attempt_failure':
                failures[f'{arm}/generation_extraction_failed'] += 1
                continue
            for split, result in p['results'].items():
                if not result['valid']:
                    failures[f'{arm}/{split}/{result.get("error_code",result.get("error","invalid"))}'] += 1
            forecast = analyses[p['analysis_id']]['forecast']
            wrong = next((r for r in p['measurement_rows']['behavior'] if r['valid_execution'] and r['predicted'] is not None and not r['correct']), None)
            if arm == 'behavior_grounded' and forecast['valid'] and forecast['code_reference_valid'] and forecast['grounding_compliant'] and wrong:
                cases.append({'seed': c['seed'], 'attempt': p['attempt'], 'candidate_id': p['candidate_id'],
                    'analysis_id': p['analysis_id'], 'state_id': wrong['state_id'], 'family': wrong['family'],
                    'predicted_node': wrong['predicted'], 'actual_node': wrong['actual'],
                    'code_reference_valid': forecast['code_reference_valid'],
                    'grounding_compliant': forecast['grounding_compliant'], 'candidate_valid': p['valid'],
                    'boundary': 'Schema-valid grounded analysis can still predict the actual code incorrectly.'})
    pooled = {arm: metrics(rows) for arm, rows in rows_by_arm.items()}
    arm_rows = []
    for arm, group in by_arm.items():
        m = pooled[arm]
        arm_rows.append({'arm': arm, 'label': LABELS[arm], 'seeds': len(group),
            'attempts': sum(c['candidate_attempts'] for c in group),
            'valid_candidates': sum(c['valid_candidates'] for c in group),
            'valid_rate': sum(c['valid_candidates'] for c in group)/sum(c['candidate_attempts'] for c in group),
            'forecast_valid': sum(c['forecast_valid_count'] for c in group),
            'mean_auc': mean(c['quality_curve']['auc'] for c in group),
            'median_auc': median(c['quality_curve']['auc'] for c in group),
            'mean_final_dev_gain': mean(c['quality_curve']['points'][-1][1] for c in group),
            'mean_heldout_gain_vs_baseline': mean((c['heldout']['baseline']['objective']-c['heldout']['incumbent']['objective'])/max(abs(c['heldout']['baseline']['objective']),1e-12) for c in group),
            'strict_traces': sum(c['strict_supported_traces'] for c in group),
            'strict_trace_cells': sum(c['strict_supported_traces'] > 0 for c in group),
            **{k: m[k] for k in ('behavior_itt_accuracy', 'behavior_conditional_accuracy', 'target_brier_itt',
                'target_brier_conditional', 'behavior_execution_coverage', 'target_label_coverage', 'ece', 'roc_auc', 'balanced_accuracy')},
            'behavior_prediction_coverage': m['prediction_coverage']['behavior'],
            'target_prediction_coverage': m['prediction_coverage']['target'],
            **m['counts'], **m['baselines']})
    contrasts = []
    for pair in summary['paired_results']:
        data = pair['pairs']
        if len(data) != len(protocol['seeds']):
            raise ValueError('missing_primary_pairs')
        auc, held, brier = ([r[key] for r in data] for key in ('quality_auc_delta','heldout_relative_gain','target_brier_reduction'))
        contrasts.append({**pair, 'positive_auc_pairs': sum(x > 0 for x in auc),
            'median_target_brier_reduction': median(brier), 'auc_median_bootstrap95': interval(auc),
            'heldout_median_bootstrap95': interval(held), 'target_loss_median_bootstrap95': interval(brier)})
    diag = summary['diagnostic']
    common_rows = []
    for name in protocol['diagnostic_program_hashes']:
        row = {'program': name, 'seeds': len(protocol['diagnostic_seeds'])}
        for arm in ARMS[1:]:
            selected = [d for d in diag if d['program'] == name and d['style'] == arm]
            row[arm] = mean(d['metrics']['behavior_macro_accuracy'] for d in selected)
            row[arm+'_target_loss'] = mean(d['metrics']['target_macro_brier'] for d in selected)
        row['delta'] = row['behavior_grounded']-row['passive']
        common_rows.append(row)
    common_seed_rows = []
    for seed in protocol['diagnostic_seeds']:
        row = {'seed': seed}
        for arm in ARMS[1:]:
            row[arm] = mean(d['metrics']['behavior_macro_accuracy'] for d in diag if d['seed'] == seed and d['style'] == arm)
        row['delta'] = row['behavior_grounded']-row['passive']
        common_seed_rows.append(row)
    common = {'programs': common_rows, 'seeds': common_seed_rows,
        'passive_accuracy': mean(r['passive'] for r in common_rows),
        'grounded_accuracy': mean(r['behavior_grounded'] for r in common_rows),
        'mean_accuracy_delta': mean(r['delta'] for r in common_rows),
        'program_cluster_mean_bootstrap95': interval([r['delta'] for r in common_rows], mean)}
    primary = next(c for c in contrasts if c['control'] == 'passive' and c['treatment'] == 'behavior_grounded')
    b, c = arm_rows[1:]
    gates = [
        {'gate': 'Integrity', 'passed': all(audit['source_integrity'].values()) and audit['returned_cells']==audit['expected_cells']==24 and audit['returned_diagnostic_rows']==audit['expected_diagnostic_rows']==36 and audit['heldout_after_global_freeze'] is True, 'rule': '完整 24 单元、36 同代码诊断；哈希、前瞻顺序和数据隔离审计通过'},
        {'gate': 'Behavior', 'passed': common['mean_accuracy_delta'] >= .05,
            'rule': '同代码 C−B 行为准确率均值 ≥5 pp', 'observed': common['mean_accuracy_delta']},
        {'gate': 'Target', 'passed': primary['median_target_brier_reduction'] > 0 and min(b['target_label_coverage'],c['target_label_coverage']) >= .90,
            'rule': '配对中位损失下降 >0，B/C 标签覆盖率均 ≥90%；披露校准适用范围', 'observed': primary['median_target_brier_reduction']},
        {'gate': 'Search', 'passed': primary['median_auc_delta'] > 0 and primary['positive_auc_pairs'] >= 6 and primary['median_heldout_gain'] >= 0 and c['valid_rate']-b['valid_rate'] >= -.05,
            'rule': '中位 AUC 增益 >0，≥6/8 种子为正；保留集不降；有效率降幅 ≤5 pp', 'observed': primary['median_auc_delta']},
        {'gate': 'Chain', 'passed': c['strict_traces'] >= 3 and c['strict_trace_cells'] >= 2,
            'rule': 'C 至少3条严格一致性链，覆盖至少2个单元；不是因果中介证明', 'observed': c['strict_traces']},
    ]
    curves = [{'budget': tick, **{arm: mean(dict(c['quality_curve']['points'])[tick] for c in by_arm[arm]) for arm in ARMS}} for tick in range(protocol['candidate_attempts']+1)]
    compact_cells = [{k: c[k] for k in ('cell_id','seed','arm','candidate_attempts','valid_candidates','forecast_valid_count','quality_curve','rq1b_metrics','incumbent_id','strict_supported_traces','heldout')} for c in cells]
    traces = [{'cell_id': c['cell_id'], **t} for c in cells for t in c['descendant_traces'] if t['strict_supported_trace']]
    unique_cases = []
    for case in sorted(cases, key=lambda x: (x['seed'],x['attempt'])):
        if case['seed'] not in {x['seed'] for x in unique_cases}:
            unique_cases.append(case)
        if len(unique_cases) == 3:
            break
    return {'schema_version': 'rq1b-readout/v1', 'study_id': summary['study_id'], 'scientific_status': 'exploratory_not_confirmation',
        'source_commit': protocol['execution_head'], 'protocol_hash': protocol['protocol_hash'],
        'summary_sha256': file_hash(run/'summary.json'), 'raw_evidence_directory': 'outputs/fme_pilot/'+run.name,
        'wall_time_seconds': summary['wall_time_seconds'], 'transport': audit['transport'],
        'execution_version': protocol.get('execution_version',1),
        'transport_recovery': protocol.get('transport_recovery'), 'arms': arm_rows, 'contrasts': contrasts,
        'common_code': common, 'gates': gates, 'all_gates_pass': all(g['passed'] for g in gates),
        'curves': curves, 'cells': compact_cells, 'strict_traces': traces, 'counterexample_cases': unique_cases,
        'failure_counts_by_suite': dict(failures), 'parse_error_counts': dict(parse_errors),
        'pooled_metrics': pooled, 'uncertainty': 'Post-run descriptive percentile bootstrap: 10000 resamples, seed83031; paired seed units for search, six hand-authored program clusters for same-code accuracy. No multiplicity correction or confirmatory inference.',
        'metric_boundary': 'ITT target metric includes loss1 for missing forecasts or unscorable comparisons; it is not ordinary Brier. Conditional Brier excludes both. AUC is left-step integrated over all16 allocated attempts; the last candidate earns no retrospective area.'}


def artifact(r, audit):
    title = 'RQ1b Behavior-Grounded Analysis'
    now = datetime.now(timezone.utc).isoformat()
    primary = next(c for c in r['contrasts'] if c['control'] == 'passive' and c['treatment'] == 'behavior_grounded')
    b, c = r['arms'][1:]
    failed = '、'.join(g['gate'] for g in r['gates'] if not g['passed']) or '无'
    verdict = '预设工程继续门槛全部通过，但尚非确认性证据。' if r['all_gates_pass'] else f'本轮没有打通“行为识别→定向预测→同预算搜索收益”的完整证据链。未通过的预设门槛：{failed}。'
    ci = primary['auc_median_bootstrap95']
    sources = [{'id': 'rq1b', 'label': 'Frozen RQ1b online evidence and read-only projection',
        'path': 'results.json', 'query': {'language': 'python', 'engine': 'Python / JSON journals',
        'query': 'python scripts/report_rq1b.py '+r['raw_evidence_directory']+' --audit '+r['audit_reference']+' --output '+r['report_directory'],
        'description': 'summary.json + hash-linked events.jsonl independently audited; Python metrics and seed-level bootstrap produce results.json. Native tables/charts below additionally execute explicitly identified SQLite JSON1 projections of that same results.json. No new model or solver execution. Source commit '+r['source_commit'],
        'tables_used': ['protocol_frozen.json','summary.json','cells/*/*/*/events.jsonl','diagnostic/*/*/*/events.jsonl',r['audit_reference']],
        'metric_definitions': [r['metric_boundary'],r['uncertainty']]}}]
    datasets = {'arms': r['arms'], 'curves': [{'budget':p['budget'],'arm':LABELS[a],'improvement':p[a]} for p in r['curves'] for a in ARMS], 'programs': r['common_code']['programs'],
        'diagnostic_seeds': r['common_code']['seeds'], 'pairs': primary['pairs'],
        'gates': [{**g,'status':'通过' if g['passed'] else '未通过'} for g in r['gates']],
        'contrasts': [{'contrast': LABELS[x['treatment']]+' − '+LABELS[x['control']],
            'auc_pp': 100*x['median_auc_delta'], 'heldout_gain': x['median_heldout_gain'],
            'positive': x['positive_auc_pairs'], 'target_loss_reduction': x['median_target_brier_reduction']} for x in r['contrasts']]}
    # Snapshot rows must be flat primitive values; detailed nested evidence remains in results.json.
    datasets = {name: [{k:v for k,v in row.items() if isinstance(v,(str,int,float,bool)) or v is None} for row in rows] for name,rows in datasets.items()}
    tables = []
    def table(tid, heading, columns, subtitle):
        tables.append({'id': tid, 'title': heading, 'subtitle': subtitle, 'showDescription': True,
            'dataset': tid, 'sourceId': 'rq1b', 'layout': 'full',
            'defaultSort':{'field':columns[0][0],'direction':'asc'},
            'columns': [{'field':key,'label':label, **({'format':fmt} if fmt else {'type':'text'})} for key,label,fmt in columns]})
    table('gates','预设继续门槛', [('gate','门槛',None),('status','结果',None),('rule','冻结规则',None)], '先冻结后评测；未按结果改门槛。通过不等于统计显著。')
    table('arms','三臂搜索与行为测量', [('label','Arm',None),('valid_candidates','有效/128','number'),('mean_auc','均值 AUC','percent'),('behavior_itt_accuracy','行为 ITT','percent'),('behavior_conditional_accuracy','行为条件准确率','percent'),('target_brier_itt','目标惩罚损失','number'),('target_brier_conditional','条件 Brier','number'),('strict_traces','严格链数','number')], '每臂8种子×16候选。条件准确率排除无效执行，ITT 不排除；二者不可混用。')
    table('programs','同一代码的行为识别：主要能力比较', [('program','外部教师诊断程序',None),('passive','B 准确率','percent'),('behavior_grounded','C 准确率','percent'),('delta','C−B','percent')], '6个人工固定程序×3独立诊断种子。每次6个状态；程序、状态一致，预测风格不同。')
    table('diagnostic_seeds','同代码诊断按状态种子展开', [('seed','诊断种子','number'),('passive','B','percent'),('behavior_grounded','C','percent'),('delta','C−B','percent')], '种子911–913均未进入算法搜索；每行平均6程序×6状态。')
    table('pairs','主要比较 C−B：八个配对种子', [('seed','种子','number'),('quality_auc_delta','AUC 差','percent'),('heldout_relative_gain','保留集相对改善','percent'),('behavior_accuracy_delta','搜索中行为差','percent'),('target_brier_reduction','目标损失下降','number')], 'AUC/行为差用比例显示：1%=1个百分点；保留集为 (B成本−C成本)/|B成本|。全部8对，不挑最好种子。')
    table('contrasts','完整三臂比较', [('contrast','比较',None),('auc_pp','中位 AUC 差/pp','number'),('heldout_gain','中位保留集改善','percent'),('positive','AUC 正向/8','number'),('target_loss_reduction','中位损失下降','number')], 'C−B 主要；B−A、C−A 次要探索。不以次要赢家替代主要假设。')
    datasets['coverage'] = [{'label': row['label'], **{k:row[k] for k in ('behavior','behavior_valid','target','target_probability_valid','target_positive','target_negative','target_label_coverage','target_prediction_coverage','ece','always_no_failure_brier','always_failure_brier','constant_half_brier')}} for row in r['arms']]
    table('coverage','分母、标签覆盖与简单基线', [('label','Arm',None),('behavior_valid','有效行为/768','number'),('target_probability_valid','可评分目标/384','number'),('target_positive','失败','number'),('target_negative','非失败','number'),('target_label_coverage','标签覆盖','percent'),('ece','池化 ECE','number'),('always_no_failure_brier','全猜非失败 Brier','number'),('always_failure_brier','全猜失败 Brier','number')], '概率或标签缺失不加入条件 Brier/校准；ITT 仍以最大惩罚1计。样本来自少量种子，不当作独立重复。')
    charts = [{'id': 'potential', 'title': '完整预算中的 incumbent 改善曲线',
        'subtitle': '8个配对种子的逐预算均值；连线仅帮助读图，统计 AUC 使用左端阶梯积分。',
        'showDescription': True, 'question': '正确识别代码行为能否改善同预算算法搜索？',
        'rationale': '17个有序预算点展示收益到达时间；最终 best 不能代替整条预算曲线。',
        'type': 'line', 'dataset': 'curves', 'sourceId': 'rq1b',
        'encodings':{'x':{'field':'budget','type':'ordinal','label':'候选槽位'},'y':{'field':'improvement','type':'quantitative','label':'开发集改善','format':'percent'},'color':{'field':'arm','type':'nominal','label':'实验臂'}},
        'xAxisTitle': '已消耗候选槽位（无效也计入）', 'yAxisTitle': '相对初始算法的开发集改善',
        'valueFormat':'percent', 'layout':'full'}]
    # These are actual local JSON1 queries, not invented warehouse provenance.
    # Python above creates the bounded statistical projection; SQL below is run
    # against that exact results.json object to populate every native visual.
    source_paths = {'gates':'$.gates','arms':'$.arms','programs':'$.common_code.programs',
        'diagnostic_seeds':'$.common_code.seeds','coverage':'$.arms','contrasts':'$.contrasts'}
    arm_case = lambda field: 'CASE '+field+''.join(" WHEN '"+arm+"' THEN '"+LABELS[arm]+"'" for arm in ARMS)+' END'
    def visual_source(name, sql):
        source_id='projection_'+name
        with sqlite3.connect(':memory:') as db:
            db.row_factory=sqlite3.Row
            datasets[name]=[dict(row) for row in db.execute(sql,{'results_json':json.dumps(r,allow_nan=False)})]
        sources.append({'id':source_id,'label':'Audited RQ1b / '+name,'path':'results.json',
            'query':{'language':'sql','engine':'SQLite JSON1 / local statistical projection','sql':sql,
                'description':'Executed by scripts/report_rq1b.py; :results_json is the exact delivered results.json, derived from '+r['raw_evidence_directory']+'/summary.json and audited journals. Python calculates metrics/paired bootstrap before this display projection. No remote database or new experiment.',
                'tables_used':['results.json'], 'metric_definitions':[r['metric_boundary'],r['uncertainty']]}})
        return source_id
    for item in tables:
        name=item['id']; row='j.value'
        if name=='pairs':
            sql="SELECT json_extract(p.value, '$.seed') AS seed, "+', '.join("json_extract(p.value, '$."+key+"') AS "+key for key in ('quality_auc_delta','heldout_relative_gain','behavior_accuracy_delta','target_brier_reduction'))+" FROM json_each(:results_json, '$.contrasts') AS c, json_each(c.value, '$.pairs') AS p WHERE json_extract(c.value, '$.control')='passive' AND json_extract(c.value, '$.treatment')='behavior_grounded' ORDER BY seed"
        else:
            expressions=[]
            for col in item['columns']:
                key=col['field']
                if key=='status': expression="CASE json_extract(j.value,'$.passed') WHEN 1 THEN '通过' ELSE '未通过' END"
                elif key=='contrast': expression=arm_case("json_extract(j.value,'$.treatment')")+" || ' − ' || "+arm_case("json_extract(j.value,'$.control')")
                elif key=='auc_pp': expression="100*json_extract(j.value,'$.median_auc_delta')"
                elif key in {'heldout_gain','positive','target_loss_reduction'}:
                    field={'heldout_gain':'median_heldout_gain','positive':'positive_auc_pairs','target_loss_reduction':'median_target_brier_reduction'}[key]
                    expression="json_extract(j.value,'$."+field+"')"
                else: expression="json_extract(j.value,'$."+key+"')"
                expressions.append(expression+' AS '+key)
            sql='SELECT '+', '.join(expressions)+" FROM json_each(:results_json, '"+source_paths[name]+"') AS j ORDER BY j.key"
        item['sourceId']=visual_source(name,sql)
    curve_sql="""SELECT json_extract(p.value,'$[0]') AS budget,
       CASE json_extract(c.value,'$.arm.id') WHEN 'scalar' THEN 'A · Scalar'
       WHEN 'passive' THEN 'B · Passive' ELSE 'C · Grounded' END AS arm,
       AVG(json_extract(p.value,'$[1]')) AS improvement,
       COUNT(*) AS seed_count, MIN(json_extract(p.value,'$[1]')) AS minimum,
       MAX(json_extract(p.value,'$[1]')) AS maximum
FROM json_each(:results_json,'$.cells') AS c,
     json_each(c.value,'$.quality_curve.points') AS p
GROUP BY budget, arm ORDER BY budget, arm"""
    charts[0]['sourceId']=visual_source('curves',curve_sql)
    blocks = []
    def md(name, body):
        blocks.append({'id':name,'type':'markdown','body':body,'sourceId':'rq1b'})
    def tb(name):
        blocks.append({'id':'table_'+name,'type':'table','tableId':name})
    md('title', '# '+title)
    blocks[-1].pop('sourceId')
    md('summary', '## 技术摘要\n\n'+verdict+f'\n\n在 CVRP24 / DeepSeek V4 Flash / 8×16 的冻结 pilot 中，同代码行为准确率 C−B 为 **{pp(r["common_code"]["mean_accuracy_delta"])}**；配对中位 Potential-AUC 差 **{pp(primary["median_auc_delta"])}**（{primary["positive_auc_pairs"]}/8 正向），保留集配对中位改善 **{pct(primary["median_heldout_gain"])}**。C 有 **{c["strict_traces"]}** 条严格一致性链，来自 {c["strict_trace_cells"]} 个单元。\n\n这是新队列的独立结果，不与旧 v7 合并；未重新启动 RQ2–RQ4。')
    tb('gates')
    md('scope','## 问题、边界与指标\n\n研究问题：强制核对代码行为，是否能比普通分析更有效地改善同预算搜索？三臂使用同一个 FME loop、EOH 生成适配器、单 elite 父代和 dev_train 选择规则。A 的分析仅影子记录；B/C 回流前瞻预测，但不回流行为探针或目标实例的实测结果。没有历史检索、跨问题迁移或模型比较。\n\nB 也回答完全相同的数值行为题、定向失败题和下一步编辑题；C 仅额外强制代码引用与 claim→behavior→condition 解释。因此本轮是“共同测量下增加 grounding 要求”，不是“无探针 B 对有探针 C”，也不能与旧 v7 被动组数值直接拼接。\n\n行为真值是候选代码实际返回的节点，不是最优节点；预测最优动作却看错代码仍算错。Target failure 指相对父算法退化或执行无效，平局不是失败。目标 ITT 损失给缺失概率/缺失参照标签记1，必须与只用可评分样本的 Brier 分开。')
    tb('arms')
    md('behavior','## 关键发现一：先排除“候选本身更容易分析”的混淆\n\n搜索中各臂产生不同代码，直接比较准确率不能独立识别分析能力。额外的同代码面板固定六个 external_teacher 程序，并让 B/C 预测相同状态；程序及结果从未注入搜索。\n\nB/C 同代码总体准确率分别为 '+f'{r["common_code"]["passive_accuracy"]:.1%} / {r["common_code"]["grounded_accuracy"]:.1%}'+ '。按程序簇重采样的描述性区间为 '+ ' 至 '.join(pp(x) for x in r['common_code']['program_cluster_mean_bootstrap95'])+'。只有六个人工模板，不能代表任意 LLM 生成程序。')
    tb('programs'); tb('diagnostic_seeds')
    md('search','## 关键发现二：用全预算轨迹判断搜索收益\n\n左阶梯 AUC = Σ(q[t−1])/16，q[t] 为截至第 t 个槽位的最好开发集相对改善。最后一轮改善进入最终 best，但不能获得过去预算的面积。全部无效候选同样消耗槽位。\n\n主要 C−B 中位 AUC 差的配对种子 bootstrap 95% 描述性区间：'+pp(ci[0])+' 至 '+pp(ci[1])+'。区间用8个种子为重采样单位，不把数百个探针伪装成独立实验；无多重比较校正，不作为显著性声明。')
    blocks.append({'id':'chart_potential','type':'chart','chartId':'potential'})
    tb('pairs'); tb('contrasts')
    md('calibration','## 关键发现三：预测、校准与算法潜力分开报告\n\n主要比较的目标惩罚损失配对中位下降为 '+f'{primary["median_target_brier_reduction"]:+.4f}'+f'。B/C 目标标签覆盖率分别为 {b["target_label_coverage"]:.1%}/{c["target_label_coverage"]:.1%}；有效候选率变化为 {pp(c["valid_rate"]-b["valid_rate"])}。\n\n下表的校准与简单基线是可评分样本池化后的描述量，不能与带缺失惩罚的 ITT 直接比较。分箱固定为5个等宽区间，仅正/负类各至少10个时报告 ECE、ROC 和 balanced accuracy。它们不是新的独立成功门槛，也不替代搜索收益。')
    tb('coverage')
    case_text = []
    for case in r['counterexample_cases']:
        case_text.append(f'- 种子 {case["seed"]}，候选槽位 {case["attempt"]}，状态 `{case["state_id"]}`：预测节点 {case["predicted_node"]}，真实代码返回 {case["actual_node"]}。引用片段存在且结构完整，仍未读对行为。候选 `{case["candidate_id"][:16]}`。')
    chain_text = []
    for trace in r['strict_traces'][:3]:
        chain_text.append(f'- `{trace["cell_id"]}` / 槽位 {trace["attempt"]}：源节点 {trace["source_actual_choice"]} → 预期编辑后节点 {trace["expected_child_choice"]} → 实际子代节点 {trace["child_actual_choice"]}；开发改善 {pct(trace["child_dev_gain"])}，定向改善 {pct(trace["child_target_gain"])}。')
    md('cases','## 可追溯机制案例\n\n按种子、槽位排序，最多展示三个不同 C 种子的首个“结构合规但行为预测错误”案例；不是按故事精彩程度挑选。完整分析 ID 与候选哈希保留在 results.json，原始响应不进入 Git。\n\n'+ ('\n'.join(case_text) or '没有满足该筛选条件的案例；不以缺失替代正确。')+'\n\n严格链要求直接父代、已回流预测、源行为预测正确、子代在同一旧状态上按预期改变，而且开发与定向结果都改善。以下最多三条按运行记录顺序展示；即使成立，也只证明轨迹一致性，不证明改进由分析因果中介。\n\n'+ ('\n'.join(chain_text) or '本轮没有严格支持链，不能把普通后代改善改称为机制证据。'))
    md('method','## 方法与复现\n\n冻结源码 `'+r['source_commit']+'`；协议哈希 `'+r['protocol_hash']+'`。搜索种子811–818，24单元，每单元16槽位；每个普通 dev_train/dev_probe 各8实例，heldout24实例。目标族 clustered_far、capacity_tight、radial_mixed 各2实例。每个候选6个行为干预状态，使用同一份四舍五入后的距离矩阵供模型读取与代码执行。状态可由合法路线前缀到达，但不保证候选自身会走到该状态。\n\n先写入前瞻分析并 fsync，再执行评测；选择仅依 dev_train，所有24 incumbent 冻结后才做同代码诊断和 heldout，之后不重排、不改代码。生成3072 token 上限、分析2048，温度0.7；两次重试只处理网络故障，不能按质量补抽。API token 消耗并不严格相等：这里控制候选次数和请求上限，不声称等 token 或等秒。\n\n8个种子、16次候选是本轮工程预算，不是文献最优值，也不是效能分析结论。代码输出预测的测量思想可参照 [CRUXEval（ICML 2024）](https://proceedings.mlr.press/v235/gu24c.html)；本轮未使用其数据、代码或性能数字。\n\n只读复核入口：`scripts/audit_rq1b.py`；报告重建：`scripts/report_rq1b.py`。精简证据在 results.json，审计回执在 agent_records/calibrations；原始日志和模型响应留在 ignored outputs，须具有该本地证据目录才能完整重放审计。')
    if r['execution_version']==2:
        blocks[-1]['body']=blocks[-1]['body'].replace('两次重试只处理网络故障，不能按质量补抽。',
            '每周期最多2次传输重试，最多3个周期（后两周期等待10/30秒），每逻辑请求最多9次HTTP；只恢复未成功的网络请求，成功但低质的输出不能补抽。已冻结上限805个逻辑请求、7245次HTTP，不代表实际全部消耗。成功响应、完整提示和父代描述原子保存；这些提供断点证据，但本轮未验证进程崩溃后的自动续跑。')
    blocks[-1]['body']=blocks[-1]['body'].replace('代码输出预测的测量思想可参照 [CRUXEval（ICML 2024）](https://proceedings.mlr.press/v235/gu24c.html)；本轮未使用其数据、代码或性能数字。','本轮不新增外部论文机制或数据。')
    transport = audit.get('transport', {})
    md('audit','## 完整性与成本\n\n'+f'运行壁钟时间 {r["wall_time_seconds"]/60:.1f} 分钟。审计通过表示记录内部一致、冻结源码匹配、预测先于评测；不等于算法正确性的数学证明。\n\n传输账本（包含预检、搜索、诊断和已记录重试）：\n\n```json\n'+json.dumps(transport,ensure_ascii=False,indent=2)+'\n```\n\n'+(f'此前中断 v1 单独消耗 {r["prior_interrupted_cost"]["http_requests"]} 次 HTTP 尝试、已知输入 {r["prior_interrupted_cost"]["known_input_tokens"]:,} / 输出 {r["prior_interrupted_cost"]["known_output_tokens"]:,} token。两轮累计 HTTP {transport["http_requests"]+r["prior_interrupted_cost"]["http_requests"]} 次。旧轮效果不并入本轮；缺失 usage 不能按零计，也不据 token 猜测账单金额。\n\n' if r.get('prior_interrupted_cost') else '')+'本轮只做必要编译、diff 检查、实际实验与只读证据审计；没有执行全量单元测试，也没有为调整审计脚本重新生成候选。真实输出审计与报告包装验证不是额外科研 cohort。')
    md('limits','## 局限、不确定性与退出条件\n\n单模型、单问题、24客户合成实例，只能说明该受限 CVRP 构造器接口。目标族仅各2个实例；代码状态探针是离线干预，不是策略访问分布。结构标签和代码子串匹配只检查格式，真正的行为能力必须靠执行真值。\n\n对话预测不是确定性随机过程；配对种子控制评测数据和探针，不能固定服务端随机采样。Prompt/style 与生成后的候选分布仍会相互影响；相同代码诊断只缓解能力测量混淆，不提供搜索增益的因果中介识别。\n\n目标错误可能来自程序无效、概率缺失、参照缺失或真正的泛化误判，必须同时看 ITT、条件指标和覆盖率。全部失败与零效果保留；不补种子、不改门槛、不按结果放宽链定义。')
    md('next','## 下一步\n\n'+ ('本轮仅达到预设工程继续条件。下一步应先独立复现 RQ1b，并扩展同代码程序覆盖；仍不把 pilot 写成已确认结论。' if r['all_gates_pass'] else '本轮停止扩展。保留 RQ1b 为唯一主线，但不恢复历史注入、迁移和模型比较，也不追加试验来把门槛“跑过去”。先依据失败门槛修订一个可检验假设，再单独冻结下一版协议。')+'\n\n可保留的系统资产：真实代码行为探针、前瞻预测日志、无泄漏三臂反馈开关、缺失显式计分和严格后代链审计。这些是可复用的研究 Agent 测量能力，不等于一个已验证有效的算法设计 Skill。')
    md('questions','## 后续问题\n\n1. 同代码上的差距主要是代码算错、变量符号读错，还是输出格式丢失？\n2. 即使读对当前行为，提出的下一步编辑能否真的改变关键决策，而不仅改变解释文字？\n3. 如果预测能力提高但 AUC 不提高，是建议本身无用，还是生成器没有执行建议？这些问题需在新冻结协议中逐一分开，不在本轮追加臂。')
    return {'surface':'report','manifest':{'version':1,'surface':'report','title':title,'description':'CVRP / Flash / 三臂前瞻分析 pilot：能力、目标预测与搜索收益分层审查',
        'generatedAt':now,'charts':charts,'tables':tables,'sources':sources,'blocks':blocks},
        'snapshot':{'version':1,'generatedAt':now,'status':'ready','datasets':datasets},'sources':sources}


def partial_artifact(audit):
    """An interrupted cohort gets an execution report, not a partial winner table."""
    if audit['protocol_hash']!='3b13dbed7e492aeafe46aa04691961e0a52f0a25700edb577004980264db0471':
        raise ValueError('partial_narrative_is_specific_to_rq1b_20260831_v1')
    title='RQ1b Interrupted Pilot'; now=datetime.now(timezone.utc).isoformat()
    sql="""SELECT json_extract(value, '$.seed') AS seed,
       json_extract(value, '$.arm') AS arm,
       json_extract(value, '$.status') AS status,
       json_extract(value, '$.evaluated_slots') AS evaluated_slots
FROM json_each(:audit_json, '$.cells')
ORDER BY seed, arm"""
    # Actual, executed JSON-to-table query used by the canonical chart/table.
    # It adds no source system: :audit_json is exactly the supplied audit JSON.
    with sqlite3.connect(':memory:') as db:
        db.row_factory=sqlite3.Row
        cell_rows=[dict(row) for row in db.execute(sql,{'audit_json':json.dumps(audit)})]
    labels={'cell_frozen':'16/16 · 已冻结','interrupted':'中断','not_started':'未启动'}
    progress=[]; counts=[]
    for seed in sorted({c['seed'] for c in cell_rows}):
        row={'seed':seed}; count_row={'seed':str(seed)}
        for c in cell_rows:
            if c['seed']==seed:
                row[c['arm']]=labels[c['status']] if c['status']!='interrupted' else f'{c["evaluated_slots"]}/16 · 中断'
                count_row[c['arm']]=c['evaluated_slots']
        progress.append(row)
        counts.append(count_row)
    source={'id':'audit','label':'Read-only partial evidence audit','path':'results.json',
        'query':{'language':'sql','engine':'SQLite JSON1 / local JSON projection','sql':sql,
            'query':'python scripts/audit_rq1b.py outputs/fme_pilot/rq1b_online_20260831_v1 --partial --output agent_records/calibrations/rq1b_online_20260831_v1_audit.json',
            'description':'Executed by scripts/report_rq1b.py with :audit_json bound to results.json (the exact audit receipt). SQL extracts status rows; Python pivots seed/arm for the table and maps labels for the chart. Cost figures are direct audit JSON fields. Source commit '+audit['source_commit']+'; historical evidence unchanged.',
            'tables_used':['json_each(:audit_json, $.cells)'],
            'metric_definitions':['Complete cell=16 evaluated slots plus cell_frozen and rq1b_cell_endpoints. Evaluation does not imply valid candidate. Started slot=action_started. No scientific effect estimated from the incomplete cohort.']}}
    tables=[{'id':'progress','title':'全部八个种子的三臂执行状态','dataset':'progress','sourceId':'audit','layout':'full',
        'subtitle':'分母均为16个候选槽位；已评测不等于算法有效。状态来自逐单元日志，而不是主线程部分汇总。','showDescription':True,
        'columns':[{'field':'seed','label':'种子','format':'number'}]+[{'field':arm,'label':LABELS[arm],'type':'text'} for arm in ARMS]}]
    blocks=[]
    def md(name,body): blocks.append({'id':name,'type':'markdown','body':body,'sourceId':'audit'})
    md('title','# '+title)
    md('summary','## 技术摘要：实验中断，不能判定三臂优劣\n\nRQ1b 的 CVRP 三臂实现、协议冻结和真实在线实验已执行，但网络请求在连接阶段反复失败，达到预设两次重试上限后停止。实际日志保留 **14个完整单元、4个部分单元、6个未启动单元**；已评测 **246/384个候选槽位**。同代码诊断 **0/36**，held-out **0/24单元**，所以行为能力、目标预测和搜索增益的完整比较均未成立。\n\n这不是 C 方法有效或无效的证据。旧 v7 与本次队列不混合；没有挑已完成种子宣布赢家，也没有追加生成把门槛跑过去。')
    md('findings','## 关键发现：14个单元已保存，主线程只回收了12个\n\n批量并发收集在遇到第一个异常时退出；同批后续已有两个单元完成并写入独立日志，却未进入主线程 summary。逐目录审计重建了真实状态，下表展示所有坐标，不修改旧 summary，也不丢弃它漏收的有效记录。')
    blocks.append({'id':'progress_chart','type':'chart','chartId':'coverage'})
    blocks.append({'id':'progress_table','type':'table','tableId':'progress'})
    md('transport','## 中断来自连接错误，不是模型质量筛选\n\n本轮共514次 HTTP 尝试：1次预检、262次生成、251次分析。其中20次失败、16次为传输重试；4个最终失败的逻辑请求各用尽1次初始尝试与2次重试。失败回执为 URLError、HTTP状态为空，不能据此断言是密钥、配额或模型拒绝。具体根因无法从经过脱敏的旧回执恢复。\n\n18.1分钟运行中记录输入1,215,418 token、输出197,977 token；20次失败请求没有 usage，不能把已知 token 和当成精确账单。已启动250个槽位，其中246个有完整候选评测；812/A 的第9个槽位生成已成功，但分析尚未取得成功响应，恢复时不应重新抽取它的代码。\n\n事后不带认证的只读连接检查可以取得 HTTP 响应，但该检查没有调用模型，不能据此声称认证服务已恢复。没有修改用户代理设置或绕过网关权限。')
    md('scope','## 已冻结的研究范围与测量口径\n\n只做 CVRP24、DeepSeek V4 Flash；A 标量反馈（影子分析不回流），B 普通被动分析，C 行为落地分析。B/C 都回答相同六个代码返回值问题、三个目标族失败预测和下一步编辑问题；C 额外要求精确代码引用与 claim→behavior→condition 结构。本轮 B 已被共同测量题增强，不能与旧版 B 数字直接合并。\n\n分析必须在代码执行前写入日志。行为真值是代码真实返回节点，而非最优动作；目标失败为执行无效或相对父算法退化，平局不是失败。缺失概率或无法比较的目标标签记最大 ITT 损失1，并与条件 Brier 分开。Potential-AUC 用全部16槽位左阶梯积分，无效候选也占预算。\n\n预定主要比较 C−B；同代码诊断六个 external_teacher 程序×三个种子×B/C，全部搜索 incumbent 冻结后才执行；之后评测 held-out。历史注入、迁移、模型比较继续暂停。')
    md('method','## 方法、完整性审计与复现\n\n冻结源码 `'+audit['source_commit']+'`；协议哈希 `'+audit['protocol_hash']+'`。所有22项冻结文件哈希仍匹配。只读审计验证了日志哈希链、传输重试顺序、候选文件哈希、前瞻预测先于评测、探针身份与目标标签重算；对14个完整单元重算了记录中的指标和左阶梯 AUC。没有重新执行候选程序或调用模型。\n\n部分审计通过只表示现有记录内部一致；不表示完整三臂比较通过、没有任何统计偏差或存在因果机制。完整队列审计分支目前只做过编译检查，因真实队列未完成而没有执行验证，不写作“全审计通过”。\n\n可复核回执：`agent_records/calibrations/rq1b_online_20260831_v1_audit.json`。原始证据位于 ignored `outputs/fme_pilot/rq1b_online_20260831_v1`，不包含在 Git 交付中；需要该本地目录才能重算审计。报告的 results.json 仅含状态、成本和哈希，不发布候选程序、模型原始响应或密钥。')
    md('limits','## 局限与不确定性：现在没有可用的效果区间\n\n缺少完整配对种子、同代码面板和 held-out，不能估计完整协议下的效果或置信区间，也不能将缺失结果补零。此处不给 C 对 B 的 AUC、行为或 Brier 胜负结论；不根据已完成子集改变后续协议或选择恢复对象。8种子与16次生成是工程预算，不是文献最优值或统计功效保证。\n\n独立单元已冻结不等于研究全局已冻结；本次尚未到达全局 held-out 门禁。所有恢复都必须保存原始 terminal=incomplete，并用独立补充协议说明网络中断与旧记录关联。')
    md('next','## 建议下一步：先修复断点记录，再批准独立重跑\n\n进一步检查发现不能保证无损续跑：EOH 的父代提示会使用 algorithm 一句描述（evolution.py 的父代格式化路径），但当前只保存代码、前瞻分析和提示哈希，没有保存该原始描述。4个中断单元的当前父代都不是初始算法，无法用固定基线描述恢复。哈希不能反推原始文本；不能由我重新编写一段描述后声称提示完全相同。\n\n因此撤回“只补剩余请求即可无损恢复”的初步方案。建议保留本轮 incomplete 为独立证据，先新增持久断点：保存完整已解析候选的描述、代码哈希、父代选择、分析回流状态、未完成请求身份和版本号；验证精确提示哈希后才可恢复。原始响应及断点仅写 ignored outputs，不写 Git。\n\n用户批准后，另立版本化协议，从头跑完整三臂，保持科学问题、每单元16槽位、模型、数据和门槛，不把本轮部分结果合并进新队列，不挑“看起来更好”的单元保留。新旧 API 成本分开且累计披露；明确一次网络重试上限和恢复上限，再启动。当前没有自行修改冻结文件、添加候选、增加重试次数或启动补跑。')
    md('questions','## 后续要核对的问题\n\n1. 网络恢复后，所有原坐标是否能按相同数据与预算完整结束？\n2. B/C 在固定同代码面板上是否真的出现行为识别差异？\n3. 若差异存在，它能否跨过目标预测、有效率、全预算搜索与严格后代链四项限制？目前这些问题均未被本轮回答。')
    return {'surface':'report','manifest':{'version':1,'surface':'report','title':title,'description':'RQ1b 在线实验中断报告：保全证据、明确缺失，不发布部分赢家',
        'generatedAt':now,'sources':[source],'tables':tables,'charts':[{'id':'coverage','title':'未完成槽位分散在不同种子与实验臂',
            'subtitle':'每根柱只表示已评测槽位数，统一目标16；不是算法效果或有效率。','showDescription':True,
            'question':'哪些配对坐标还不足16次评测，因而不能汇成完整三臂比较？',
            'rationale':'八个种子与三臂的24个预算坐标同时比较，显示缺失并非完整的配对子队列。',
            'intent':'comparison','type':'bar','dataset':'counts','sourceId':'audit','layout':'full',
            'encodings':{'x':{'field':'seed','type':'ordinal','label':'配对种子'},'y':{'field':'evaluated','type':'quantitative','label':'已评测槽位'},'color':{'field':'arm','type':'nominal','label':'实验臂'}},
            'xAxisTitle':'配对种子','yAxisTitle':'已评测候选槽位（目标16）','valueFormat':'number',
            'referenceLines':[{'axis':'y','value':16,'label':'冻结预算16','lineStyle':'dashed','color':'neutral'}]}],'blocks':blocks},
        'snapshot':{'version':1,'generatedAt':now,'status':'partial','datasets':{'progress':progress,'counts':[{'seed':r['seed'],'arm':LABELS[a],'evaluated':r[a]} for r in counts for a in ARMS]}},'sources':[source]}


def partial_execution_artifact(audit):
    """Evidence-based v2 interruption readout; no partial effect estimates."""
    title='RQ1b API Execution Report'; now=datetime.now(timezone.utc).isoformat()
    transport=audit['transport']; datasets={}; sources=[]; tables=[]; blocks=[]
    def source(name,path,fields):
        sql='SELECT '+', '.join("json_extract(value,'$."+f+"') AS "+f for f in fields)+" FROM json_each(:audit_json,'$."+path+"') ORDER BY key"
        with sqlite3.connect(':memory:') as db:
            db.row_factory=sqlite3.Row
            datasets[name]=[dict(row) for row in db.execute(sql,{'audit_json':json.dumps(audit,allow_nan=False)})]
        sources.append({'id':name,'label':'RQ1b v2 read-only audit / '+name,'path':'results.json',
            'query':{'language':'sql','engine':'SQLite JSON1 / local audit JSON','sql':sql,
                'description':'Executed against the exact delivered results.json audit receipt; upstream '+audit['raw_evidence_directory']+'/summary.json and all hash-linked journals. No model or solver execution in the report.',
                'tables_used':['results.json'], 'metric_definitions':['Slots evaluated include invalid candidates; no partial effect estimate is authorized. Token sums exclude unknown usage; historical cohorts are not pooled.']}})
    source('progress','cells',['seed','arm','status','evaluated_slots','started_slots','requests','failed_requests'])
    source('failures','failure_receipts',['cell_id','purpose','http_status','error_code','transport_attempt','elapsed_seconds'])
    for name,title_text,cols in [
        ('progress','完整24坐标的执行状态',[('seed','种子','number'),('arm','实验臂',None),('status','状态',None),('evaluated_slots','已评测/16','number'),('started_slots','已启动/16','number'),('requests','HTTP尝试','number')]),
        ('failures','所有失败请求：未隐藏或记作零成本',[('cell_id','单元',None),('purpose','用途',None),('http_status','HTTP状态','number'),('error_code','错误类别',None),('transport_attempt','周期内次数','number'),('elapsed_seconds','耗时/秒','number')])]:
        tables.append({'id':name,'title':title_text,'dataset':name,'sourceId':name,'layout':'full',
            'defaultSort':{'field':cols[0][0],'direction':'asc'},
            'columns':[{'field':f,'label':label,**({'format':fmt} if fmt else {'type':'text'})} for f,label,fmt in cols]})
    def md(name,body): blocks.append({'id':name,'type':'markdown','body':body,'sourceId':'progress'})
    blocks.append({'id':'title','type':'markdown','body':'# '+title})
    md('summary',f'## 技术摘要：已实际调用 API，但完整对比仍未完成\n\n独立 v2 队列完成 **{audit["locally_frozen_cells"]}/24 个完整单元**，另有 **{audit["interrupted_cells"]} 个部分单元、{audit["not_started_cells"]} 个未启动单元**；已评测 **{audit["evaluated_slots"]}/{audit["planned_candidate_slots"]} 个候选槽位**。同代码诊断 **0/36**，held-out **0/24**。本报告不发布任何三臂优劣、配对效应或成功门判定。\n\nOpenCode Go / DeepSeek V4 Flash 已实际运行，不是 dry-run。发生 HTTP 200 响应流中的 JSON 解析错误，传输层将其归类为不可重试，固定队列在当前批收尾后停止。这既不能证明模型拒绝，也不能证明 C 方法有效或无效。')
    md('scope','## 研究范围与口径\n\n只做 CVRP24。A 为标量反馈、分析影子留存；B 回流普通前瞻分析；C 在相同预测任务上增加精确代码引用及 claim→behavior→condition 要求。每臂8个配对种子，每单元16个候选；失败/无效候选也占槽位。B/C 不读取行为探针或目标实例实测结果，只回流事前预测。\n\n行为标签是代码实际返回值，不是最佳动作；定向失败是执行无效或相对父算法退化，平局不是失败。最终研究目标是同代码行为识别→定向预测→全预算 Potential-AUC，而不是解释文笔或最终 best。由于队列中断，本报告只报告执行事实。')
    blocks.append({'id':'coverage_chart','type':'chart','chartId':'coverage'})
    blocks.append({'id':'progress_table','type':'table','tableId':'progress'})
    md('finding',f'## 关键发现：收集与断点已改善，流式协议处理仍阻塞\n\n本轮独立日志保存 {audit["locally_frozen_cells"]} 个完整单元，主线程也回收 {audit["summary_returned_cells"]} 个；不再因为一个 future 失败漏收同批其他结果。成功响应、完整提示、请求参数以及含原始描述的父代状态已经保存并经只读哈希复核。\n\n失败位于流式传输 JSON 解析，不是对完整模型输出进行评分时失败。HTTP 200 只表示服务器接受并开始响应，不能保证整条响应流正确结束。当前证据不能进一步区分网关输出异常、流截断或客户端 SSE 解析边界问题。没有保存错误分片，不能臆造更细的根因。')
    blocks.append({'id':'failure_table','type':'table','tableId':'failures'})
    md('cost',f'## 成本与预算\n\n本轮壁钟时间 {audit["wall_time_seconds"]/60:.1f} 分钟，HTTP 尝试 {transport["http_requests"]} 次，其中失败 {transport["failed_http"]} 次，传输重试 {transport["retry_http"]} 次。已知输入 {transport["known_input_tokens"]:,}、输出 {transport["known_output_tokens"]:,} token；{transport["requests_missing_usage"]} 次请求缺少 usage，不能当作零，也不能据此推算精确账单。\n\n冻结上限是805个逻辑请求、每请求最多9次HTTP（每周期2次内层重试，最多3个周期），并非本轮实际全部耗尽。此次 JSON 解析错误在第一周期即被判不可重试；未为了完成队列擅自改变冻结错误分类或增加 API 调用。8种子、16候选是工程预算，不是文献最优值或统计功效保证。'+ (f'\n\n旧 v1 中断队列另有 {audit["prior_interrupted_cost"]["http_requests"]} 次 HTTP、已知输入 {audit["prior_interrupted_cost"]["known_input_tokens"]:,} / 输出 {audit["prior_interrupted_cost"]["known_output_tokens"]:,} token。两轮累计 {transport["http_requests"]+audit["prior_interrupted_cost"]["http_requests"]} 次 HTTP；成本单独列示、效果绝不合并。' if audit.get('prior_interrupted_cost') else ''))
    md('audit','## 完整性、复现与验证边界\n\n冻结执行提交 `'+audit['source_commit']+'`，协议哈希 `'+audit['protocol_hash']+'`。只读审计核对源码、日志链、候选文件、前瞻顺序、探针身份、标签重算、完整单元 AUC，以及 v2 成功响应/状态断点。没有重新执行候选程序或调用模型；这不是完整队列的科学有效性证明。\n\n原始证据位于 `'+audit['raw_evidence_directory']+'`（Git 忽略），精简审计为 `agent_records/calibrations/rq1b_online_20260831_v2_audit.json`。复核命令：`python scripts/audit_rq1b.py '+audit['raw_evidence_directory']+' --partial`。没有运行全量测试；代码只做必要编译检查。自动崩溃恢复尚未实现或验证，持久断点不能被写作“已验证无损续跑”。')
    md('limits','## 局限与不能得出的结论\n\n缺少完整八组配对、36条同代码诊断和24个保留集评测，不能判断行为识别、Brier、校准或搜索收益谁更好。不能把未启动槽位当作算法失败，也不能只挑已完成种子估算胜率。与旧 v1、旧 RQ1–RQ4 的数据保持独立。所有失败和原始终态保留，未为了过门槛改种子、预算或案例。')
    md('next','## 下一步需要的批准\n\n仅提出传输层补充协议：将“未取得完整响应”的流解析失败纳入有界恢复，并用已保存的成功响应重放及逐提示哈希校验恢复状态；不重新抽取成功输出，不追加候选，不提高原有每请求9次上限。原始 incomplete 队列不可覆盖，续跑必须单独保留证据关联。\n\n当前补充协议等待用户确认，未启动续跑。若精确提示或状态重建不一致，应停止并报告差异，不能由人工补写父代描述后称为无损。RQ2–RQ4 及 Phase 6 继续暂停。')
    md('questions','## 后续核对问题\n\n1. 失败来自非法 SSE 分片、截断，还是客户端按行解析的边界？需要在获批恢复中记录脱敏诊断，不增加独立科研请求。\n2. 已完成请求重放后，生成提示、父代选择及当前状态能否逐项匹配？\n3. 仅在全队列完成后，C 能否同时跨过行为识别、目标预测、AUC、有效率及严格后代链门槛？')
    chart={'id':'coverage','title':'各配对种子的候选评测进度','subtitle':'每臂每种子目标16；图中是执行覆盖，不是算法成绩。','showDescription':True,
        'question':'缺失评测分布在哪些种子和实验臂？','rationale':'24坐标同时展示，避免把完整单元误当作完整配对队列。',
        'intent':'comparison','type':'bar','dataset':'progress','sourceId':'progress','layout':'full',
        'encodings':{'x':{'field':'seed','type':'ordinal','label':'配对种子'},'y':{'field':'evaluated_slots','type':'quantitative','label':'已评测槽位'},'color':{'field':'arm','type':'nominal','label':'实验臂'}},
        'xAxisTitle':'配对种子','yAxisTitle':'已评测候选槽位 / 16','valueFormat':'number',
        'referenceLines':[{'axis':'y','value':16,'label':'固定预算16','lineStyle':'dashed','color':'neutral'}]}
    return {'surface':'report','manifest':{'version':1,'surface':'report','title':title,'description':'真实 API 实验中断后的可复核执行报告；不发布部分赢家',
        'generatedAt':now,'sources':sources,'tables':tables,'charts':[chart],'blocks':blocks},
        'snapshot':{'version':1,'generatedAt':now,'status':'partial','datasets':datasets},'sources':sources}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir',type=Path)
    parser.add_argument('--audit',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--partial',action='store_true')
    args = parser.parse_args()
    audit = read(args.audit)
    if args.partial:
        if audit['status']!='partial_integrity_verified': raise ValueError('partial_audit_required')
        result=dict(audit)
        if audit.get('execution_version')==2:
            prior=Path(__file__).resolve().parents[1]/'agent_records/calibrations/rq1b_online_20260831_v1_audit.json'
            if prior.exists(): result['prior_interrupted_cost']=read(prior)['transport']
            payload=partial_execution_artifact(result)
        else: payload=partial_artifact(audit)
    else:
        result = project(args.run_dir,audit)
        root=Path(__file__).resolve().parents[1]
        result['audit_reference']=args.audit.resolve().relative_to(root).as_posix()
        result['report_directory']=args.output.resolve().relative_to(root).as_posix()
        prior=root/'agent_records/calibrations/rq1b_online_20260831_v1_audit.json'
        if result['execution_version']==2 and prior.exists():
            result['prior_interrupted_cost']=read(prior)['transport']
        payload = artifact(result,audit)
    args.output.mkdir(parents=True,exist_ok=True)
    for name,value in [('results.json',result),('artifact.json',payload)]:
        (args.output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'status':'partial_projection_created' if args.partial else 'projection_created',
        'all_gates_pass':result.get('all_gates_pass'),'result_hash':digest(result),'gates':result.get('gates')},ensure_ascii=False))


if __name__ == '__main__':
    main()
