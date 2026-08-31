"""RQ1b：同一个 FME loop 内的 CVRP 三臂被动反馈实验。旧 v7 不改写。"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from statistics import median

from eoh_rag.experiments.provider import load_local_env
from eoh_rag.fme.analysis import QuestionStack, ResearchQuestion
from eoh_rag.fme.archives import FMEArchives
from eoh_rag.fme.behavior_analysis import build_analysis_prompt, forecast_outcomes, metrics, parse_forecast
from eoh_rag.fme.behavior_probes import TARGET_DESCRIPTIONS, build_probe_panel, build_target_suites, execute_behavior
from eoh_rag.fme.controller import FMEAction
from eoh_rag.fme.mainline import GenerationRequest
from eoh_rag.fme.online_adapters import ROOT, ChatCompletionTransport, EOHGeneratorAdapter, EvidenceJournal, FixtureTransport, ProviderFailure, digest, file_hash, verify_journal
from eoh_rag.fme.online_pilot import FixedGenerationController, PilotCell
from eoh_rag.fme.pilot_evaluation import SubprocessEvaluator, build_suite, get_problem_spec
from eoh_rag.fme.potential import AnalysisOutcome, QualityObservation
from eoh_rag.fme.research_loop import FMEResearchLoop, ReplayActionResult


def diagnostic_programs():
    """外部编写的诊断程序，不是研究 Agent 发现，不进入搜索或胜负表。"""
    header = ('def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):\n')
    bodies = {
        'nearest': '    return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]\n',
        'depot_positive': '    s = distance_matrix[current_node][unvisited_nodes] + 0.7 * distance_matrix[depot][unvisited_nodes]\n    return unvisited_nodes[np.argmin(s)]\n',
        'depot_negative': '    s = distance_matrix[current_node][unvisited_nodes] - 0.7 * distance_matrix[depot][unvisited_nodes]\n    return unvisited_nodes[np.argmin(s)]\n',
        'high_demand': '    s = distance_matrix[current_node][unvisited_nodes] / (demands[unvisited_nodes] + 1.0)\n    return unvisited_nodes[np.argmin(s)]\n',
        'early_return': '    if current_node != depot and rest_capacity < 15:\n        return depot\n    return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]\n',
        'normalized_sum': '    d = distance_matrix[current_node][unvisited_nodes]\n    h = distance_matrix[depot][unvisited_nodes]\n    s = d / (np.max(d) + 1e-9) + 0.5 * h / (np.max(h) + 1e-9)\n    return unvisited_nodes[np.argmin(s)]\n',
    }
    return {name: header + body for name, body in bodies.items()}


def load_and_freeze(path: Path, fixture=False):
    p = json.loads(path.read_text(encoding='utf-8'))
    if p['schema_version'] != 'fme-rq1b/v1' or p['problems'] != ['cvrp_construct']:
        raise ValueError('rq1b_cvrp_only')
    if [a['id'] for a in p['arms']] != ['scalar','passive','behavior_grounded'] or len(set(p['seeds'])) != len(p['seeds']):
        raise ValueError('invalid_rq1b_coordinates')
    if any(a['controller'] not in {'scalar','passive'} for a in p['arms']):
        raise ValueError('rq1b_fixed_generation_only')
    p['mode'] = 'integration_smoke' if fixture else 'online'
    if fixture:
        p.update(seeds=[6001], candidate_attempts=3, action_tick_cap=3, development_instances_per_suite=2,
                 heldout_instances=2, sizes={'cvrp_construct':12}, target_instances_per_family=1,
                 diagnostic_seeds=[6101], diagnostic_programs=2)
    load_local_env()
    model = 'integration-fixture/primary' if fixture else os.environ.get(p['model_env'],'').strip()
    if not fixture and model != p['required_model']:
        raise ValueError('rq1b_requires_declared_flash_model')
    p['resolved_model'] = model
    p['execution_head'] = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    sources = ['eoh_rag/fme/'+name+'.py' for name in (
        'rq1b','behavior_analysis','behavior_probes','online_pilot','online_adapters','pilot_evaluation',
        'research_loop','controller','archives','potential','mainline','problem_adapters','analysis','cold_start')]
    sources += ['scripts/rq1b_probe_worker.py','scripts/fme_pilot_eval_worker.py',
        'eoh_rag/experiments/provider.py','eoh_rag/experiments/research_contracts.py',
        'official_eoh/eoh/src/eoh/eoh/evolution.py','official_eoh/examples/cvrp_construct/prob.py',
        p['contract'],str(path.relative_to(ROOT)).replace('\\','/')]
    p['source_hashes'] = {name:file_hash(ROOT/name) for name in sources}
    p['suite_hashes'],p['panel_hashes'] = {},{}
    for seed in p['seeds']:
        for split in ('dev_train','dev_probe','heldout'):
            count = p['heldout_instances'] if split=='heldout' else p['development_instances_per_suite']
            p['suite_hashes'][f'{seed}/{split}'] = build_suite('cvrp_construct',seed,split,count,p['sizes']['cvrp_construct'])['content_hash']
        for family,suite in target_suites(p,seed).items():
            p['suite_hashes'][f'{seed}/target/{family}'] = suite['content_hash']
        for attempt in range(1,p['candidate_attempts']+1):
            p['panel_hashes'][f'{seed}/{attempt}'] = build_probe_panel(seed,attempt)['content_hash']
    programs = dict(list(diagnostic_programs().items())[:p['diagnostic_programs']])
    p['diagnostic_program_hashes'] = {name:digest(code) for name,code in programs.items()}
    for seed in p['diagnostic_seeds']:
        p['panel_hashes'][f'diagnostic/{seed}'] = build_probe_panel(seed,0)['content_hash']
        for family,suite in target_suites(p,seed).items():
            p['suite_hashes'][f'diagnostic/{seed}/{family}'] = suite['content_hash']
    p['expected_cells'] = len(p['seeds'])*len(p['arms'])
    p['expected_diagnostic_rows'] = len(p['diagnostic_seeds'])*len(programs)*2
    p['protocol_hash'] = digest(p)
    return p


def target_suites(p,seed):
    return build_target_suites(seed,p['target_split'],p['target_instances_per_family'],p['sizes']['cvrp_construct'])


def transport_for(p,journal,spec):
    if p['mode']=='integration_smoke':
        return FixtureTransport(p['resolved_model'],journal,spec)
    return ChatCompletionTransport(p['resolved_model'],journal,temperature=p['temperature'],
        generation_tokens=p['generation_max_tokens'],analysis_tokens=p['analysis_max_tokens'],
        timeout=p['provider_timeout_seconds'],provider=p['provider'],thinking=p['thinking'],
        stream=p['stream'],network_retries=p['network_retries'])


def forecast_request(transport,prompt,panel,code,fixture):
    if not fixture:
        return transport.request(prompt,purpose='analysis',problem='cvrp_construct')
    receipt={'purpose':'analysis','prompt_hash':digest(prompt),'model':transport.model,'network_request':False,'ok':True}
    transport.usage.append(receipt)
    transport.journal.append('fixture_request',receipt)
    first=panel['states'][0]
    return json.dumps({'explanation':'claim: fixture; behavior: wiring only; condition: no scientific evidence',
        'predicted_effect':0.01,'predicted_success_probability':0.4,
        'behavior_predictions':{s['state_id']:s['unvisited_nodes'][0] for s in panel['states']},
        'targeted_predictions':{f:{'failure_probability':0.6,'predicted_effect':-0.01} for f in TARGET_DESCRIPTIONS},
        'next_edit':{'instruction':'fixture only','probe_id':first['state_id'],'expected_node':first['unvisited_nodes'][0],
                     'target_family':next(iter(TARGET_DESCRIPTIONS))},'code_evidence':code.splitlines()[0]})


def empty_outcomes(panel):
    return {'behavior':[{'family':s['family'],'state_id':s['state_id'],'correct':False,'predicted':None,
                         'actual':None,'valid_execution':False} for s in panel['states']],
            'targeted':[{'family':f,'probability':None,'actual_failure':1,'actual_gain':None,
                         'predicted_effect':None,'brier':1.0,'prediction_missing':True} for f in TARGET_DESCRIPTIONS]}


class RQ1bCell(PilotCell):
    """复用 PilotCell 的档案、动作账本和 run；只替换前瞻分析及固定测量适配器。"""
    def __init__(self,p,arm,seed,directory):
        self.protocol,self.arm,self.problem,self.seed=p,arm,'cvrp_construct',seed
        self.fixture=p['mode']=='integration_smoke'
        self.actor='integration_fixture' if self.fixture else 'research_agent'
        self.journal=EvidenceJournal(directory,actor=self.actor)
        self.spec=get_problem_spec(self.problem)
        self.evaluator=SubprocessEvaluator(p['evaluator_timeout_seconds'])
        self.suites={s:build_suite(self.problem,seed,s,p['development_instances_per_suite'],p['sizes'][self.problem]) for s in ('dev_train','dev_probe')}
        self.targets=target_suites(p,seed)
        for split,suite in self.suites.items():
            if suite['content_hash']!=p['suite_hashes'][f'{seed}/{split}']: raise ValueError('suite_drift')
        for family,suite in self.targets.items():
            if suite['content_hash']!=p['suite_hashes'][f'{seed}/target/{family}']: raise ValueError('target_drift')
        self.transport=transport_for(p,self.journal,self.spec)
        self.generator=EOHGeneratorAdapter(self.spec,self.transport)
        self.loop=FMEResearchLoop(FixedGenerationController())
        self.archives=FMEArchives(directory/'archives')
        self.attempts=self.failures=self.valid=self.solver_calls=self.counterexample_searches=0
        self.pending_probe=self.latest=None
        self.repair_attempted_claims=set()
        self.feedback=self.last_analysis=''
        self.questions=QuestionStack(self.problem,(ResearchQuestion('initial','Can code-grounded prediction improve this candidate lineage?',100),))
        self.analysis_outcomes,self.observations,self.population=[],[],[]
        self.initial_objective=0.0
        self.retrieved_item_ids=()
        self.rq_outcomes={'behavior':[],'targeted':[]}
        self.lineage=[]
        self.prior=None
        self.scalar_feedback={}
        self.forecast_valid_count=0
        self.behavior_worker_calls=0

    def evaluate_targets(self,code):
        result={}
        for family,suite in self.targets.items():
            self.solver_calls+=1
            result[family]=self.evaluator.evaluate(self.problem,code,suite)
        return result

    def behavior(self,code,panel):
        self.behavior_worker_calls+=1
        return execute_behavior(code,panel,self.protocol['evaluator_timeout_seconds'])

    def start(self):
        state=super().start()
        targets=self.evaluate_targets(self.spec['baseline_code'])
        if not all(r['valid'] for r in targets.values()): raise ValueError('target_baseline_invalid')
        self.population[0]['target_results']=targets
        self.journal.append('external_teacher_target_baseline',targets)
        return state

    def context(self,parent):
        context='\nPrevious attempt scalar feedback:\n'+json.dumps(self.scalar_feedback,ensure_ascii=False)
        included=self.arm['id']!='scalar' and self.prior is not None
        if included:
            # 只回流评测前写下的预测，不给生成器任何 probe/target 的实测标签。
            context+='\nPrevious prospective analysis, unverified; may refer to a rejected candidate:\n'+json.dumps(self.prior['forecast']['fields'],ensure_ascii=False)
        exposure={'attempt':self.attempts,'parent_ids':[parent['candidate_id']],
            'included_forecast':included,'source_analysis_id':self.prior['analysis_id'] if included else None,
            'source_candidate_id':self.prior['candidate_id'] if included else None,
            'generation_context':context,'context_hash':digest(context),
            'boundary':'no observed behavior or targeted outcomes; no history retrieval'}
        self.journal.append('feedback_exposure',exposure)
        return context,exposure

    def generate(self,action):
        self.attempts+=1
        panel=build_probe_panel(self.seed,self.attempts)
        if panel['content_hash']!=self.protocol['panel_hashes'][f'{self.seed}/{self.attempts}']: raise ValueError('panel_drift')
        parent=self.population[0]
        context,exposure=self.context(parent)
        self.generator.parents=[parent]
        req=GenerationRequest(self.problem,action.value,(parent['candidate_id'],),
            (self.suites['dev_train']['content_hash'],digest(parent['results']['dev_train'])),context)
        try:
            generated=self.generator.generate(req)
        except ProviderFailure:
            raise
        except (ValueError,TypeError,KeyError,AttributeError,SyntaxError):
            generated=()
        if len(generated)!=1:
            self.failures+=1
            rows=empty_outcomes(panel)
            for key in rows: self.rq_outcomes[key].extend(rows[key])
            receipt=self.journal.append('candidate_attempt_failure',{'attempt':self.attempts,'error_code':'generation_extraction_failed','measurement_rows':rows})
            self.scalar_feedback={'valid':False,'error':'generation_extraction_failed'}
            self.prior=None
            self.observations.append(QualityObservation(self.attempts,self.population[0]['objective']))
            return ReplayActionResult(action,'failed',(receipt,),failure_hash=receipt)
        candidate=generated[0]
        candidate_id=digest(candidate.code)
        code_path=self.journal.save_candidate(candidate_id,candidate.code)
        parent_summary=json.dumps({'objective':parent['objective'],'candidate_id':parent['candidate_id'],
                                   'code':parent['code'],'scope':'ordinary_dev_train_only'})
        prompt=build_analysis_prompt(self.arm['analysis_style'],candidate.code,parent_summary,panel,TARGET_DESCRIPTIONS)
        raw=forecast_request(self.transport,prompt,panel,candidate.code,self.fixture)
        forecast=parse_forecast(raw,panel,TARGET_DESCRIPTIONS,candidate.code,self.arm['analysis_style'])
        self.forecast_valid_count+=int(forecast['valid'])
        analysis={'candidate_id':candidate_id,'parent_candidate_ids':[parent['candidate_id']],
            'prompt_hash':digest(prompt),'response_hash':digest(raw),'forecast':forecast,'panel':panel,
            'target_suite_hashes':{f:s['content_hash'] for f,s in self.targets.items()},
            'visible_scope':'dev_only','actor':self.actor}
        analysis['analysis_id']='rq1b-analysis-'+digest(analysis)[:20]
        analysis_hash=self.journal.append('prospective_analysis',analysis)
        # 无论预测解析是否完整，都在 fsync 后评测代码；避免只评容易分析的程序。
        ordinary=self.evaluate(candidate.code)
        behavior=self.behavior(candidate.code,panel)
        targets=self.evaluate_targets(candidate.code)
        rows=forecast_outcomes(forecast,behavior,targets,parent['target_results'],self.protocol['epsilon'])
        for key in rows: self.rq_outcomes[key].extend(rows[key])
        valid=all(r['valid'] for r in ordinary.values())
        receipt=self.journal.append('candidate_evaluation',{'attempt':self.attempts,'candidate_id':candidate_id,
            'analysis_id':analysis['analysis_id'],'analysis_event_hash':analysis_hash,'code_path':code_path,
            'generation_prompt_hash':self.generator.last_prompt_hash,'results':ordinary,'valid':valid,
            'behavior':behavior,'target_results':targets,'measurement_rows':rows,
            'parent_target_results_hash':digest(parent['target_results'])})
        gain=(parent['objective']-ordinary['dev_train']['objective'])/max(abs(parent['objective']),1e-12) if valid else None
        if self.prior is not None:
            prior=self.prior
            # 对同一旧 panel 评测后代，仅作溯源。A 也付出相同测量成本，不回流。
            child_behavior=self.behavior(candidate.code,prior['panel'])
            edit=prior['forecast'].get('fields',{}).get('next_edit',{})
            probe=edit.get('probe_id'); family=edit.get('target_family')
            source_choice=prior['behavior'].get('choices',{}).get(probe)
            child_choice=child_behavior.get('choices',{}).get(probe)
            source_prediction=prior['forecast'].get('fields',{}).get('behavior_predictions',{}).get(probe)
            target_gain=next((r['actual_gain'] for r in rows['targeted'] if r['family']==family),None)
            direct=prior['candidate_id']==parent['candidate_id']
            strict=bool(exposure['included_forecast'] and direct and source_choice is not None and source_prediction==source_choice
                and edit.get('expected_node')!=source_choice and child_choice==edit.get('expected_node')
                and gain is not None and gain>self.protocol['epsilon'] and target_gain is not None and target_gain>self.protocol['epsilon'])
            trace={'source_analysis_id':prior['analysis_id'],'source_candidate_id':prior['candidate_id'],
                'child_id':candidate_id,'attempt':self.attempts,'direct_parent':direct,'feedback_exposed':exposure['included_forecast'],
                'source_panel_hash':prior['panel']['content_hash'],'probe_id':probe,'target_family':family,
                'source_predicted_choice':source_prediction,'source_actual_choice':source_choice,
                'expected_child_choice':edit.get('expected_node'),'child_actual_choice':child_choice,
                'child_dev_gain':gain,'child_target_gain':target_gain,'strict_supported_trace':strict,
                'boundary':'trace consistency, not proof of causal mediation'}
            self.lineage.append(trace)
            self.journal.append('descendant_trace',{'trace':trace,'child_behavior_on_source_panel':child_behavior})
        self.prior={'candidate_id':candidate_id,'analysis_id':analysis['analysis_id'],'forecast':forecast,'panel':panel,'behavior':behavior}
        self.scalar_feedback={'valid':valid,'dev_train_objective':ordinary['dev_train']['objective'],'relative_gain':gain}
        if valid:
            self.valid+=1
            fields=forecast['fields']
            if fields.get('predicted_effect') is not None and fields.get('predicted_success_probability') is not None:
                self.analysis_outcomes.append(AnalysisOutcome(analysis['analysis_id'],fields['predicted_effect'],fields['predicted_success_probability'],gain))
            row={'candidate_id':candidate_id,'algorithm':candidate.algorithm,'code':candidate.code,'objective':ordinary['dev_train']['objective'],
                 'results':ordinary,'target_results':targets,'other_inf':None}
            if candidate_id not in {p['candidate_id'] for p in self.population}:
                self.population.append(row)
                self.archive_algorithm(row)
            self.population.sort(key=lambda p:(p['objective'],p['candidate_id']))
        else:
            self.failures+=1
        self.observations.append(QualityObservation(self.attempts,self.population[0]['objective']))
        return ReplayActionResult(action,'completed' if valid else 'failed',(receipt,),failure_hash=None if valid else receipt)

    def run(self):
        result=super().run()
        result.update(rq1b_metrics=metrics(self.rq_outcomes),forecast_valid_count=self.forecast_valid_count,
            behavior_worker_calls=self.behavior_worker_calls,strict_supported_traces=sum(t['strict_supported_trace'] for t in self.lineage),
            descendant_traces=self.lineage)
        self.journal.append('rq1b_cell_endpoints',{k:result[k] for k in ('rq1b_metrics','forecast_valid_count','behavior_worker_calls','strict_supported_traces')})
        result['journal_integrity']=verify_journal(self.journal.path)
        return result


def run_diagnostic(p,directory):
    programs=dict(list(diagnostic_programs().items())[:p['diagnostic_programs']])
    coordinates=[(seed,name,style) for seed in p['diagnostic_seeds'] for name in programs for style in ('passive','behavior_grounded')]
    random.Random(92711).shuffle(coordinates)
    def one(coord):
        seed,name,style=coord
        journal=EvidenceJournal(directory/str(seed)/name/style,actor='integration_fixture' if p['mode']=='integration_smoke' else 'research_agent')
        spec=get_problem_spec('cvrp_construct'); code=programs[name]; panel=build_probe_panel(seed,0)
        if panel['content_hash']!=p['panel_hashes'][f'diagnostic/{seed}'] or digest(code)!=p['diagnostic_program_hashes'][name]: raise ValueError('diagnostic_drift')
        targets=target_suites(p,seed)
        if any(s['content_hash']!=p['suite_hashes'][f'diagnostic/{seed}/{f}'] for f,s in targets.items()): raise ValueError('diagnostic_target_drift')
        transport=transport_for(p,journal,spec)
        prompt=build_analysis_prompt(style,code,json.dumps({'code':spec['baseline_code'],'scope':'external_teacher_reference_not_search_parent'}),panel,TARGET_DESCRIPTIONS)
        raw=forecast_request(transport,prompt,panel,code,p['mode']=='integration_smoke')
        forecast=parse_forecast(raw,panel,TARGET_DESCRIPTIONS,code,style)
        prospective={'analysis_id':f'diagnostic-{seed}-{name}-{style}','candidate_id':digest(code),
            'prompt_hash':digest(prompt),'response_hash':digest(raw),'panel':panel,'forecast':forecast,'code_actor':'external_teacher'}
        journal.append('diagnostic_prospective',prospective)
        ev=SubprocessEvaluator(p['evaluator_timeout_seconds'])
        behavior=execute_behavior(code,panel,p['evaluator_timeout_seconds'])
        observed={f:ev.evaluate('cvrp_construct',code,s) for f,s in targets.items()}
        parent={f:ev.evaluate('cvrp_construct',spec['baseline_code'],s) for f,s in targets.items()}
        if not all(r['valid'] for r in parent.values()): raise ValueError('diagnostic_parent_invalid')
        rows=forecast_outcomes(forecast,behavior,observed,parent,p['epsilon'])
        result={'seed':seed,'program':name,'style':style,'candidate_id':digest(code),'forecast_valid':forecast['valid'],
                'metrics':metrics(rows),'rows':rows,'behavior':behavior,'target_results':observed,'parent_targets':parent}
        journal.append('diagnostic_evaluation',result)
        result['journal_integrity']=verify_journal(journal.path)
        return result
    rows=[]
    with ThreadPoolExecutor(max_workers=p['cell_concurrency']) as pool:
        for result in pool.map(one,coordinates):
            rows.append(result)
            print(json.dumps({'event':'common_code_diagnostic','completed':len(rows),'expected':len(coordinates)}),flush=True)
    return rows


def paired_results(p,cells):
    indexed={(r['seed'],r['arm']['id']):r for r in cells}
    results=[]
    for left,right in [('scalar','passive'),('passive','behavior_grounded'),('scalar','behavior_grounded')]:
        pairs=[]
        for seed in p['seeds']:
            a,b=indexed.get((seed,left)),indexed.get((seed,right))
            if not a or not b or not a.get('heldout_valid') or not b.get('heldout_valid'): continue
            x,y=a['heldout']['incumbent']['objective'],b['heldout']['incumbent']['objective']
            pairs.append({'seed':seed,'quality_auc_delta':b['quality_curve']['auc']-a['quality_curve']['auc'],
                'heldout_relative_gain':(x-y)/max(abs(x),1e-12),
                'behavior_accuracy_delta':b['rq1b_metrics']['behavior_macro_accuracy']-a['rq1b_metrics']['behavior_macro_accuracy'],
                'target_brier_reduction':a['rq1b_metrics']['target_macro_brier']-b['rq1b_metrics']['target_macro_brier']})
        results.append({'control':left,'treatment':right,'pairs':pairs,'missing_seeds':[s for s in p['seeds'] if s not in {r['seed'] for r in pairs}],
            'median_auc_delta':median(r['quality_auc_delta'] for r in pairs) if len(pairs)==len(p['seeds']) else None,
            'median_heldout_gain':median(r['heldout_relative_gain'] for r in pairs) if len(pairs)==len(p['seeds']) else None})
    return results


def run(p,directory):
    started=time.monotonic()
    journal=EvidenceJournal(directory,actor='integration_fixture' if p['mode']=='integration_smoke' else 'research_agent')
    journal.append('protocol_frozen',p)
    (directory/'protocol_frozen.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
    cells=[]; runtime={}; diagnostics=[]; error=None
    try:
        if p['mode']!='integration_smoke':
            t=transport_for(p,journal,get_problem_spec('cvrp_construct'))
            t.request('Reply only OK.',purpose='preflight',problem='none')
        coords=[(seed,arm) for seed in p['seeds'] for arm in p['arms']]
        random.Random(310827).shuffle(coords)
        def one(coord):
            seed,arm=coord
            cell=RQ1bCell(p,arm,seed,directory/'cells'/'cvrp_construct'/str(seed)/arm['id'])
            return cell,cell.run()
        with ThreadPoolExecutor(max_workers=p['cell_concurrency']) as pool:
            for offset in range(0,len(coords),p['cell_concurrency']):
                for cell,result in pool.map(one,coords[offset:offset+p['cell_concurrency']]):
                    cells.append(result); runtime[result['cell_id']]=cell
                    journal.append('cell_completed',{'cell_id':result['cell_id'],'result_hash':digest(result)})
                    print(json.dumps({'event':'cell_completed','cell_id':result['cell_id'],'completed':len(cells),
                        'expected':p['expected_cells'],'valid':result['valid_candidates'],'attempts':result['candidate_attempts']}),flush=True)
        if len(cells)!=p['expected_cells'] or any(c['status']!='completed' for c in cells): raise ValueError('incomplete_candidate_budget')
        journal.append('all_incumbents_frozen',{r['cell_id']:r['incumbent_id'] for r in cells})
        diagnostics=run_diagnostic(p,directory/'diagnostic')
        journal.append('common_code_panel_complete',{'rows':len(diagnostics),'hash':digest(diagnostics)})
        for result in cells:
            cell=runtime[result['cell_id']]
            suite=build_suite('cvrp_construct',cell.seed,'heldout',p['heldout_instances'],p['sizes']['cvrp_construct'])
            if suite['content_hash']!=p['suite_hashes'][f'{cell.seed}/heldout']: raise ValueError('heldout_drift')
            result['heldout']={'incumbent':cell.evaluator.evaluate(cell.problem,cell.population[0]['code'],suite),
                               'baseline':cell.evaluator.evaluate(cell.problem,cell.spec['baseline_code'],suite)}
            result['heldout_valid']=all(r['valid'] for r in result['heldout'].values())
            journal.append('heldout_evaluation',{'cell_id':result['cell_id'],'incumbent_id':result['incumbent_id'],'results':result['heldout']})
    except Exception as exc:
        error={'error_code':exc.error_code if isinstance(exc,ProviderFailure) else type(exc).__name__,
               'detail':str(exc)[:200]}
        journal.append('study_interrupted',error)
    source_matches={name:file_hash(ROOT/name)==sha for name,sha in p['source_hashes'].items()}
    complete=error is None and len(cells)==p['expected_cells'] and len(diagnostics)==p['expected_diagnostic_rows'] and all(c.get('heldout_valid') for c in cells) and all(source_matches.values())
    result={'status':('integration_smoke_completed' if p['mode']=='integration_smoke' else 'pilot_completed') if complete else 'incomplete',
        'scientific_claim_allowed':complete and p['mode']=='online','study_id':p['study_id'],'protocol_hash':p['protocol_hash'],
        'mode':p['mode'],'expected_cells':p['expected_cells'],'completed_cells':len(cells),
        'expected_diagnostic_rows':p['expected_diagnostic_rows'],'completed_diagnostic_rows':len(diagnostics),
        'cells':cells,'diagnostic':diagnostics,'source_integrity':source_matches,'terminal_error':error,
        'paired_results':paired_results(p,cells),'wall_time_seconds':time.monotonic()-started}
    journal.append('study_terminal',{'summary_hash':digest(result),'status':result['status']})
    result['journal_integrity']=verify_journal(journal.path)
    (directory/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=ROOT/'eoh_rag_workspace/experiments/manifests/refactor0830_rq1b_v1.json')
    parser.add_argument('--output',type=Path,required=True)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--execute',action='store_true')
    mode.add_argument('--integration-smoke',action='store_true')
    args=parser.parse_args()
    p=load_and_freeze(args.manifest.resolve(),args.integration_smoke)
    if args.execute or args.integration_smoke:
        result=run(p,args.output.resolve())
    else:
        args.output.mkdir(parents=True,exist_ok=False)
        (args.output/'protocol_frozen.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
        result={'status':'prepared_not_executed','protocol_hash':p['protocol_hash']}
    print(json.dumps({k:result[k] for k in ('status','protocol_hash','completed_cells','completed_diagnostic_rows','terminal_error','wall_time_seconds') if k in result}),flush=True)
    return 0 if result['status'] in {'pilot_completed','integration_smoke_completed','prepared_not_executed'} else 2


if __name__=='__main__':
    raise SystemExit(main())
