"""Read-only RQ1b evidence audit. No provider, solver or candidate execution."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from statistics import median
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eoh_rag.fme.online_adapters import ROOT, digest, file_hash, verify_journal
from eoh_rag.fme.behavior_analysis import build_analysis_prompt, metrics
from eoh_rag.fme.behavior_probes import build_probe_panel, build_target_suites, TARGET_DESCRIPTIONS
from eoh_rag.fme.pilot_evaluation import build_suite, get_problem_spec
from eoh_rag.fme.rq1b import diagnostic_programs
from scripts.audit_fme_pilot import require, verify_transport_retries

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def _verify_v2_recovery(events, protocol, checkpoint_root, allow_terminal_failure=False, allow_stream_json=False):
    """Validate outer durable cycles in addition to the v1 inner retries."""
    recovery = protocol.get('transport_recovery', {})
    expected_policy={'additional_cycles': 2, 'delays_seconds': [10, 30],
                     'max_http_attempts_per_logical_request': 9}
    require(all(recovery.get(k)==v for k,v in expected_policy.items()),
            'v2_recovery_policy_mismatch')
    max_inner = protocol['network_retries'] + 1
    active = None; next_ordinal = 1; checkpoints = set(); final_cell_hash = None
    for event in events:
        kind, payload = event['kind'], event['payload']
        if kind == 'cell_checkpoint_saved':
            require(event.get('actor') == 'research_agent' and payload.get('path') == 'cell_checkpoint.json', 'cell_checkpoint_identity_mismatch')
            final_cell_hash = payload.get('content_hash')
            continue
        if kind == 'recovery_started':
            require(active is None or (not active.get('finished') and not active.get('ok')), 'recovery_cycle_overlap')
            cycle = payload.get('cycle'); require(cycle in (1, 2, 3), 'recovery_cycle_invalid')
            if active is not None:
                require(cycle == active['cycle'] + 1, 'recovery_cycle_nonsequential')
                require(payload.get('delay_seconds') == recovery['delays_seconds'][cycle - 2], 'recovery_delay_mismatch')
                require(active['attempt'] == max_inner and not active.get('ok'), 'recovery_before_inner_exhaustion')
                failed=active['last_request']; status=failed.get('http_status'); code=failed.get('error_code')
                require(status in {408,429,500,502,503,504} or code in {'stream_total_timeout','stream_missing_terminal_marker','URLError','OSError','TimeoutError','ConnectionResetError','ConnectionAbortedError','BrokenPipeError','SSLError','RemoteDisconnected'} or (allow_stream_json and status==200 and code=='JSONDecodeError'), 'recovery_after_nonretryable_failure')
                require(all(payload.get(k) == active[k] for k in ('model','purpose','problem','prompt_hash')), 'recovery_identity_changed')
            else:
                require(cycle == 1 and payload.get('delay_seconds') == 0, 'recovery_initial_cycle_invalid')
            active = {'cycle': cycle, 'model': payload.get('model'), 'purpose': payload.get('purpose'),
                      'problem': payload.get('problem'), 'prompt_hash': payload.get('prompt_hash'),
                      'attempt': 0, 'total_attempts': (active.get('total_attempts', 0) if active else 0),
                      'ok': False, 'finished': False}
        elif kind == 'model_request':
            require(active is not None and not active['finished'], 'request_without_recovery_cycle')
            attempt = payload.get('transport_attempt', 1)
            require(1 <= attempt <= max_inner and attempt == active['attempt'] + 1, 'inner_retry_sequence_invalid')
            active['total_attempts'] += 1
            require(active['total_attempts'] <= recovery['max_http_attempts_per_logical_request'], 'outer_retry_budget_exceeded')
            require(all(payload.get(k) == active[k] for k in ('model', 'purpose', 'problem', 'prompt_hash')),
                    'recovery_request_identity_mismatch')
            active['attempt'] = attempt; active['ok'] = bool(payload.get('ok')); active['last_request'] = payload
            if active['ok']: active['finished'] = True
        elif kind == 'checkpoint_saved':
            require(active is not None and active['finished'] and active['ok'], 'checkpoint_without_success')
            ordinal = payload.get('ordinal'); require(ordinal == next_ordinal, 'checkpoint_ordinal_mismatch')
            rel = payload.get('path'); require(isinstance(rel, str) and Path(rel).name == rel and rel.endswith('.json'), 'checkpoint_path_invalid')
            target = (checkpoint_root / rel).resolve()
            require(target.parent == checkpoint_root.resolve() and target.is_file(), 'checkpoint_missing')
            data = json.loads(target.read_text(encoding='utf-8'))
            require(data.get('schema_version')=='rq1b-request-checkpoint/v1' and data.get('protocol_hash')==protocol['protocol_hash'] and data.get('actor')==event['actor'], 'checkpoint_protocol_or_actor_mismatch')
            require(data.get('ordinal') == ordinal and data.get('prompt_hash') == active['prompt_hash'], 'checkpoint_request_identity_mismatch')
            require(data.get('model') == active['model'] and data.get('purpose') == active['purpose'] and data.get('problem') == active['problem'], 'checkpoint_request_shape_mismatch')
            spec=data.get('request_spec'); expected_spec={'model':protocol['resolved_model'],'purpose':active['purpose'],'problem':active['problem'],'max_tokens':64 if active['purpose']=='preflight' else (protocol['analysis_max_tokens'] if active['purpose']=='analysis' else protocol['generation_max_tokens']),'temperature':protocol['temperature'],'thinking':protocol['thinking'],'stream':protocol['stream'],'provider':protocol['provider'],'prompt_hash':active['prompt_hash'],'response_format':{'type':'json_object'} if active['purpose']=='analysis' and protocol['resolved_model'].startswith('deepseek') else None,'reasoning':{'effort':'none'} if protocol['provider']=='opencode-go' and protocol['thinking']=='disabled' else None,'stream_options':{'include_usage':True} if protocol['stream'] else None}
            require(spec == expected_spec, 'checkpoint_request_spec_mismatch')
            require(data.get('prompt_hash') == digest(data.get('prompt', '')) and data.get('response_hash') == digest(data.get('response', '')) and data.get('request_spec_hash') == digest(data.get('request_spec')), 'checkpoint_hash_mismatch')
            require(payload.get('prompt_hash') == data['prompt_hash'] and payload.get('response_hash') == data['response_hash'] and payload.get('request_spec_hash') == data['request_spec_hash'], 'checkpoint_event_hash_mismatch')
            require(rel not in checkpoints, 'duplicate_checkpoint_path'); checkpoints.add(rel); next_ordinal += 1
            active = None
    require(active is None or (allow_terminal_failure and active.get('last_request') and not active['ok'] and any(e['kind']=='action_aborted' for e in events)), 'unterminated_recovery_cycle')
    require({p.name for p in checkpoint_root.glob('request-*.json')}==checkpoints,'unreceipted_success_checkpoint')
    if final_cell_hash is not None:
        target=checkpoint_root.parent / 'cell_checkpoint.json'; require(target.is_file(), 'cell_checkpoint_missing')
        data=json.loads(target.read_text(encoding='utf-8')); saved_hash=data.pop('content_hash',None)
        require(data.get('protocol_hash') == protocol['protocol_hash'] and saved_hash == digest(data) == final_cell_hash, 'cell_checkpoint_hash_mismatch')


def records(path, protocol, check_v2=True, allow_stream_json=False):
    verify_journal(path)
    result = [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]
    verify_transport_retries(result, protocol['network_retries'])
    if check_v2 and protocol.get('execution_version') == 2:
        _verify_v2_recovery(result, protocol, path.parent / 'checkpoints',allow_stream_json=allow_stream_json)
    return result

def outer_retry_count(events):
    cycle=1; count=0
    for event in events:
        if event['kind']=='recovery_started': cycle=event['payload']['cycle']
        elif event['kind']=='model_request' and cycle>1 and event['payload'].get('transport_attempt',1)==1: count+=1
    return count

def equal(a, b):
    if isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(b,(int,float)) and not isinstance(b,bool):
        return math.isclose(a,b,abs_tol=1e-12,rel_tol=1e-12)
    if isinstance(a,dict) and isinstance(b,dict):
        return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
    if isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)):
        return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    return a==b

def measured_rows(forecast, behavior, target, parent, epsilon):
    """Reconstruct labels without invoking the runtime outcome adapter."""
    fields=forecast['fields']; states={r['state_id']:r for r in behavior.get('state_results',[])}
    result={'behavior':[],'targeted':[]}
    for sid,predicted in fields['behavior_predictions'].items():
        actual=behavior.get('choices',{}).get(sid,states.get(sid,{}).get('choice'))
        valid=bool(states.get(sid,{}).get('valid',actual is not None))
        result['behavior'].append({'family':fields['behavior_families'][sid],'state_id':sid,
            'correct':bool(valid and predicted is not None and predicted==actual),
            'predicted':predicted,'actual':actual,'valid_execution':valid})
    for family,prediction in fields['targeted_predictions'].items():
        observed,reference=target[family],parent[family]
        reference_valid=reference['valid'] and isinstance(reference['objective'],(int,float)) and math.isfinite(reference['objective'])
        gain=(reference['objective']-observed['objective'])/max(abs(reference['objective']),epsilon) if reference_valid and observed['valid'] else None
        label=1 if not observed['valid'] else int(gain < -epsilon) if gain is not None else None
        probability=prediction['failure_probability']
        result['targeted'].append({'family':family,'probability':probability,'actual_failure':label,
            'actual_gain':gain,'predicted_effect':prediction['predicted_effect'],
            'brier':1.0 if probability is None or label is None else (probability-label)**2,
            'prediction_missing':probability is None,'reference_missing':not reference_valid})
    return result

def failed_rows(panel):
    return {'behavior':[{'family':s['family'],'state_id':s['state_id'],'correct':False,'predicted':None,
        'actual':None,'valid_execution':False} for s in panel['states']],
        'targeted':[{'family':f,'probability':None,'actual_failure':1,'actual_gain':None,
            'predicted_effect':None,'brier':1.0,'prediction_missing':True} for f in TARGET_DESCRIPTIONS]}

def panel_check(panel, expected):
    body={k:v for k,v in panel.items() if k!='content_hash'}
    sha=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    require(sha==panel['content_hash']==expected,'panel_content_mismatch')

def forecast_check(forecast, panel):
    fields=forecast.get('fields',{})
    states={str(s['state_id']):s for s in panel['states']}
    behavior=fields.get('behavior_predictions',{}); families=fields.get('behavior_families',{})
    require(set(behavior)==set(states)==set(families), 'forecast_state_domain_mismatch')
    require(all(families[sid]==str(state['family']) for sid,state in states.items()),'forecast_family_domain_mismatch')
    for sid,value in behavior.items():
        require(value is None or (isinstance(value,int) and not isinstance(value,bool) and value in set(states[sid]['unvisited_nodes'])|{0}), 'forecast_node_domain_mismatch')
    targeted=fields.get('targeted_predictions',{})
    require(set(targeted)==set(TARGET_DESCRIPTIONS), 'forecast_target_domain_mismatch')
    for prediction in targeted.values():
        probability=prediction.get('failure_probability')
        require(probability is None or (isinstance(probability,(int,float)) and not isinstance(probability,bool) and math.isfinite(probability) and 0 <= probability <= 1), 'forecast_probability_invalid')
        effect=prediction.get('predicted_effect')
        require(effect is None or (isinstance(effect,(int,float)) and not isinstance(effect,bool) and math.isfinite(effect) and effect<=1),'forecast_target_effect_invalid')
    effect=fields.get('predicted_effect'); success=fields.get('predicted_success_probability')
    require(effect is None or (isinstance(effect,(int,float)) and not isinstance(effect,bool) and math.isfinite(effect) and effect<=1), 'forecast_effect_invalid')
    require(success is None or (isinstance(success,(int,float)) and not isinstance(success,bool) and math.isfinite(success) and 0 <= success <= 1), 'forecast_success_probability_invalid')

def suite_check(results, hashes):
    require(set(results)==set(hashes),'suite_family_mismatch')
    for name,result in results.items():
        require(result.get('suite_hash')==hashes[name],'result_suite_hash_mismatch')
        objective=result.get('objective',result.get('candidate_objective'))
        if result.get('valid', True):
            require(isinstance(objective,(int,float)) and not isinstance(objective,bool) and math.isfinite(objective), 'objective_not_finite')

def audit(run_dir, *, allow_stream_json=False):
    summary,protocol=read(run_dir/'summary.json'),read(run_dir/'protocol_frozen.json')
    require(summary['status'] in {'pilot_completed','integration_smoke_completed'},'study_not_complete')
    require(digest({k:v for k,v in protocol.items() if k!='protocol_hash'})==protocol['protocol_hash'],'protocol_hash_mismatch')
    if protocol.get('execution_version') == 2:
        require({'eoh_rag/fme/rq1b_v2.py','eoh_rag/fme/rq1b_transport.py'} <= set(protocol.get('source_hashes',{})), 'v2_runner_sources_missing')
        head=protocol.get('execution_head','')
        require(isinstance(head,str) and len(head)==40 and all(c in '0123456789abcdef' for c in head.lower()), 'execution_commit_invalid')
        require(subprocess.run(['git','cat-file','-e',head+'^{commit}'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0,'execution_commit_missing')
        expected_recovery={'additional_cycles': 2, 'delays_seconds': [10, 30], 'max_http_attempts_per_logical_request': 9}
        require(all(protocol.get('transport_recovery',{}).get(k)==v for k,v in expected_recovery.items()), 'v2_recovery_policy_missing')
    source={n:(ROOT/n).is_file() and file_hash(ROOT/n)==h for n,h in protocol['source_hashes'].items()}
    require(all(source.values()),'frozen_source_mismatch')
    study=records(run_dir/'events.jsonl',protocol,allow_stream_json=allow_stream_json)
    require(study[0]['kind']=='protocol_frozen' and equal(study[0]['payload'],protocol),'initial_protocol_mismatch')
    expected={(seed,arm['id']) for seed in protocol['seeds'] for arm in protocol['arms']}
    cells={(c['seed'],c['arm']['id']):c for c in summary['cells']}
    require(len(summary['cells'])==len(cells)==protocol['expected_cells'] and set(cells)==expected,'cell_coordinates_mismatch')
    require(len(list((run_dir/'cells').glob('*/*/*/events.jsonl')))==len(cells),'cell_journal_count_mismatch')
    completions=[e for e in study if e['kind']=='cell_completed']
    require(len(completions)==len(cells) and {e['payload'].get('cell_id') for e in completions}==set(c['cell_id'] for c in summary['cells']), 'cell_completion_coordinates_mismatch')
    requests=[e['payload'] for e in study if e['kind']=='model_request']; outer_retries=outer_retry_count(study)
    spec=get_problem_spec('cvrp_construct'); baseline_id=digest(spec['baseline_code']); cell_checks=[]
    for (seed,arm),cell in sorted(cells.items()):
        path=run_dir/'cells'/cell['cell_id']; stream=records(path/'events.jsonl',protocol,allow_stream_json=allow_stream_json); outer_retries += outer_retry_count(stream)
        ordinary_hashes={s:protocol['suite_hashes'][f'{seed}/{s}'] for s in ('dev_train','dev_probe')}
        target_hashes={f:protocol['suite_hashes'][f'{seed}/target/{f}'] for f in TARGET_DESCRIPTIONS}
        for split,h in ordinary_hashes.items():
            require(build_suite('cvrp_construct',seed,split,protocol['development_instances_per_suite'],protocol['sizes']['cvrp_construct'])['content_hash']==h,'ordinary_data_drift')
        rebuilt=build_target_suites(seed,protocol['target_split'],protocol['target_instances_per_family'],protocol['sizes']['cvrp_construct'])
        require({f:s['content_hash'] for f,s in rebuilt.items()}==target_hashes,'target_data_drift')
        initial_event=next(e for e in stream if e['kind']=='external_teacher_baseline')
        initial=initial_event['payload']['dev_train']['objective']; suite_check(initial_event['payload'],ordinary_hashes)
        baseline_targets=next(e['payload'] for e in stream if e['kind']=='external_teacher_target_baseline'); suite_check(baseline_targets,target_hashes)
        population={baseline_id:{'objective':initial,'code':spec['baseline_code'],'targets':baseline_targets}}
        best_id=baseline_id; prior=None; scalar={}; attempts=[]; all_rows={'behavior':[],'targeted':[]}
        analyses={}; evaluations={}; seen_attempts=set(); traces=[]; points=[[0,0.0]]; local_requests=[]; exposure=None; forecast_count=0
        for event in stream:
            k,p=event['kind'],event['payload']
            if k=='model_request':
                requests.append(p); local_requests.append(p)
            elif k=='feedback_exposure':
                attempt=len(attempts)+1
                require(p['attempt']==attempt and p['parent_ids']==[best_id],'feedback_parent_or_attempt_mismatch')
                included=arm!='scalar' and prior is not None
                require(p['included_forecast']==included,'feedback_arm_scope_mismatch')
                context='\nPrevious attempt scalar feedback:\n'+json.dumps(scalar,ensure_ascii=False)
                if included:
                    context+='\nPrevious prospective analysis, unverified; may refer to a rejected candidate:\n'+json.dumps(prior['forecast']['fields'],ensure_ascii=False)
                require(context==p['generation_context'] and digest(context)==p['context_hash'],'feedback_exact_context_mismatch')
                require(p['source_analysis_id']==(prior['analysis_id'] if included else None) and p['source_candidate_id']==(prior['candidate_id'] if included else None),'feedback_source_mismatch')
                exposure=p
            elif k=='prospective_analysis':
                require(exposure is not None,'analysis_without_generation_exposure')
                attempt=len(attempts)+1
                require(attempt not in seen_attempts, 'duplicate_attempt')
                panel_check(p['panel'],protocol['panel_hashes'][f'{seed}/{attempt}'])
                require(equal(build_probe_panel(seed,attempt),p['panel']),'panel_rebuild_mismatch')
                forecast_check(p['forecast'],p['panel'])
                require(p['target_suite_hashes']==target_hashes and p['parent_candidate_ids']==[best_id],'analysis_parent_or_target_mismatch')
                code=(path/'candidates'/f'{p["candidate_id"]}.py').read_text(encoding='utf-8')
                require(digest(code)==p['candidate_id'],'prospective_code_hash_mismatch')
                parent_summary=json.dumps({'objective':population[best_id]['objective'],'candidate_id':best_id,'code':population[best_id]['code'],'scope':'ordinary_dev_train_only'})
                prompt=build_analysis_prompt(cell['arm']['analysis_style'],code,parent_summary,p['panel'],TARGET_DESCRIPTIONS)
                require(digest(prompt)==p['prompt_hash'],'analyst_prompt_reconstruction_mismatch')
                if protocol['mode']=='online':
                    require(local_requests[-1]['ok'] and local_requests[-1]['purpose']=='analysis' and local_requests[-1]['prompt_hash']==p['prompt_hash'],'analysis_request_identity_mismatch')
                require(p['analysis_id']=='rq1b-analysis-'+digest({key:value for key,value in p.items() if key!='analysis_id'})[:20],'analysis_identity_mismatch')
                require(p['analysis_id'] not in analyses, 'duplicate_analysis_id')
                analyses[p['analysis_id']]=event; seen_attempts.add(attempt); forecast_count+=bool(p['forecast']['valid'])
            elif k in {'candidate_evaluation','candidate_attempt_failure'}:
                attempt=len(attempts)+1
                require(p['attempt']==attempt and exposure is not None,'attempt_sequence_mismatch')
                require(p['attempt'] not in {x.get('attempt') for x in attempts}, 'duplicate_attempt')
                attempts.append(p); parent=population[best_id]
                if k=='candidate_attempt_failure':
                    rows=failed_rows(build_probe_panel(seed,attempt)); scalar={'valid':False,'error':'generation_extraction_failed'}; prior=None
                else:
                    ap=analyses[p['analysis_id']]
                    require(ap['content_hash']==p['analysis_event_hash'] and ap['sequence']<event['sequence'],'prospective_order_mismatch')
                    ap=ap['payload']; cp=(path/p['code_path']).resolve()
                    require(cp.is_relative_to(path.resolve()) and digest(cp.read_text(encoding='utf-8'))==p['candidate_id'],'candidate_file_mismatch')
                    require(p['candidate_id']==ap['candidate_id'],'candidate_identity_mismatch')
                    require(p['behavior']['panel_hash']==ap['panel']['content_hash'],'executed_panel_mismatch')
                    require(p['parent_target_results_hash']==digest(parent['targets']),'parent_target_reference_mismatch')
                    suite_check(p['results'],ordinary_hashes); suite_check(p['target_results'],target_hashes)
                    require(p['valid']==all(x['valid'] for x in p['results'].values()),'candidate_validity_mismatch')
                    rows=measured_rows(ap['forecast'],p['behavior'],p['target_results'],parent['targets'],protocol['epsilon'])
                    require(len(rows['behavior'])==6 and len(rows['targeted'])==3,'measurement_denominator_mismatch')
                    gain=(parent['objective']-p['results']['dev_train']['objective'])/max(abs(parent['objective']),1e-12) if p['valid'] else None
                    evaluations[ap['analysis_id']]={'evaluation':p,'analysis':ap,'parent_id':best_id,'gain':gain,'exposure':exposure,'prior':prior}
                    prior={**ap,'behavior':p['behavior']}
                    scalar={'valid':p['valid'],'dev_train_objective':p['results']['dev_train']['objective'],'relative_gain':gain}
                    if p['valid']:
                        population.setdefault(p['candidate_id'],{'objective':p['results']['dev_train']['objective'],'code':cp.read_text(encoding='utf-8'),'targets':p['target_results']})
                        best_id=min(population,key=lambda key:(population[key]['objective'],key))
                    if protocol['mode']=='online':
                        generation=[r for r in local_requests if r['purpose']=='generation' and r['ok']][-1]
                        require(generation['prompt_hash']==p['generation_prompt_hash'],'generation_request_hash_mismatch')
                require(equal(rows,p['measurement_rows']),'measurement_rows_recalculation_mismatch')
                for key in all_rows: all_rows[key].extend(rows[key])
                points.append([attempt,(initial-population[best_id]['objective'])/max(abs(initial),1e-12)])
                exposure=None
            elif k=='descendant_trace':
                t=p['trace']; current=next(v for v in evaluations.values() if v['evaluation']['attempt']==t['attempt'])
                old=current['prior']; require(old is not None,'trace_without_prior')
                edit=old['forecast']['fields']['next_edit']; probe=edit['probe_id']; family=edit['target_family']
                source_choice=old['behavior'].get('choices',{}).get(probe)
                prediction=old['forecast']['fields']['behavior_predictions'].get(probe)
                child_behavior=p['child_behavior_on_source_panel']; child_choice=child_behavior.get('choices',{}).get(probe)
                require(child_behavior['panel_hash']==old['panel']['content_hash'],'descendant_panel_mismatch')
                target_gain=next((r['actual_gain'] for r in current['evaluation']['measurement_rows']['targeted'] if r['family']==family),None)
                direct=old['candidate_id']==current['parent_id']; exposed=current['exposure']['included_forecast']; gain=current['gain']
                strict=bool(exposed and direct and source_choice is not None and prediction==source_choice and edit['expected_node']!=source_choice and child_choice==edit['expected_node'] and gain is not None and gain>protocol['epsilon'] and target_gain is not None and target_gain>protocol['epsilon'])
                expected_trace={'source_analysis_id':old['analysis_id'],'source_candidate_id':old['candidate_id'],
                    'child_id':current['evaluation']['candidate_id'],'attempt':t['attempt'],'direct_parent':direct,'feedback_exposed':exposed,
                    'source_panel_hash':old['panel']['content_hash'],'probe_id':probe,'target_family':family,
                    'source_predicted_choice':prediction,'source_actual_choice':source_choice,'expected_child_choice':edit['expected_node'],
                    'child_actual_choice':child_choice,'child_dev_gain':gain,'child_target_gain':target_gain,'strict_supported_trace':strict,
                    'boundary':'trace consistency, not proof of causal mediation'}
                require(equal(t,expected_trace),'strict_trace_recalculation_mismatch'); traces.append(t)
        require(len(attempts)==protocol['candidate_attempts']==cell['candidate_attempts'],'candidate_budget_mismatch')
        require(sum(bool(p.get('valid')) for p in attempts)==cell['valid_candidates'],'valid_count_mismatch')
        require(best_id==cell['incumbent_id'] and not cell['retrieved_item_ids'],'incumbent_or_retrieval_mismatch')
        curve={'initial_objective':initial,'points':points,'auc':sum(p[1] for p in points[:-1])/protocol['candidate_attempts']}
        require(equal(curve,cell['quality_curve']),'step_auc_recalculation_mismatch')
        require(equal(metrics(all_rows),cell['rq1b_metrics']),'metrics_recalculation_mismatch')
        require(equal(traces,cell['descendant_traces']) and sum(t['strict_supported_trace'] for t in traces)==cell['strict_supported_traces'],'trace_summary_mismatch')
        require(forecast_count==cell['forecast_valid_count'],'forecast_count_mismatch')
        freezes=[e for e in stream if e['kind']=='cell_frozen']; require(len(freezes)==1 and freezes[0]['payload']['incumbent_id']==best_id,'cell_freeze_mismatch')
        completions=[e for e in study if e['kind']=='cell_completed' and e['payload']['cell_id']==cell['cell_id']]
        require(len(completions)==1,'cell_completion_count_mismatch')
        completed=completions[0]
        original={k:v for k,v in cell.items() if k not in {'heldout','heldout_valid'}}
        require(completed['payload']['result_hash']==digest(original),'cell_result_hash_mismatch')
        cell_checks.append({'cell_id':cell['cell_id'],'attempts':len(attempts),'valid':cell['valid_candidates'],
            'requests':len(local_requests),'forecast_events':len(evaluations),'strict_traces':cell['strict_supported_traces'],
            'journal_terminal_hash':verify_journal(path/'events.jsonl')['terminal_hash']})
    freeze=[e for e in study if e['kind']=='all_incumbents_frozen']; held=[e for e in study if e['kind']=='heldout_evaluation']
    require(len(freeze)==1 and freeze[0]['payload']=={c['cell_id']:c['incumbent_id'] for c in cells.values()},'global_freeze_mismatch')
    require(len(held)==len(cells) and all(e['sequence']>freeze[0]['sequence'] for e in held),'heldout_order_or_count_mismatch')
    for cell in cells.values():
        e=next(e for e in held if e['payload']['cell_id']==cell['cell_id'])
        require(e['payload']['incumbent_id']==cell['incumbent_id'] and equal(e['payload']['results'],cell['heldout']),'heldout_identity_mismatch')
        suite=build_suite('cvrp_construct',cell['seed'],'heldout',protocol['heldout_instances'],protocol['sizes']['cvrp_construct'])
        require(suite['content_hash']==protocol['suite_hashes'][f'{cell["seed"]}/heldout'],'heldout_data_drift')
        require(cell['heldout_valid'] and all(x['valid'] and x['suite_hash']==suite['content_hash'] for x in cell['heldout'].values()),'heldout_invalid')
    diagnostics=summary['diagnostic']; programs=dict(list(diagnostic_programs().items())[:protocol['diagnostic_programs']])
    coordinates={(s,n,a) for s in protocol['diagnostic_seeds'] for n in programs for a in ('passive','behavior_grounded')}
    require(len(diagnostics)==protocol['expected_diagnostic_rows']==len(coordinates) and {(d['seed'],d['program'],d['style']) for d in diagnostics}==coordinates,'diagnostic_coordinates_mismatch')
    for d in diagnostics:
        path=run_dir/'diagnostic'/str(d['seed'])/d['program']/d['style']/'events.jsonl'; stream=records(path,protocol,allow_stream_json=allow_stream_json); outer_retries += outer_retry_count(stream)
        requests.extend(e['payload'] for e in stream if e['kind']=='model_request')
        before=[e for e in stream if e['kind']=='diagnostic_prospective']; after=[e for e in stream if e['kind']=='diagnostic_evaluation']
        require(len(before)==len(after)==1 and before[0]['sequence']<after[0]['sequence'],'diagnostic_prospective_order_mismatch')
        ap=before[0]['payload']; panel_check(ap['panel'],protocol['panel_hashes'][f'diagnostic/{d["seed"]}'])
        forecast_check(ap['forecast'],ap['panel'])
        code=programs[d['program']]
        require(digest(code)==d['candidate_id']==ap['candidate_id']==protocol['diagnostic_program_hashes'][d['program']],'diagnostic_code_mismatch')
        prompt=build_analysis_prompt(d['style'],code,json.dumps({'code':spec['baseline_code'],'scope':'external_teacher_reference_not_search_parent'}),ap['panel'],TARGET_DESCRIPTIONS)
        require(digest(prompt)==ap['prompt_hash'] and ap['code_actor']=='external_teacher','diagnostic_prompt_or_actor_mismatch')
        require(d['behavior']['panel_hash']==ap['panel']['content_hash'],'diagnostic_execution_panel_mismatch')
        hashes={f:protocol['suite_hashes'][f'diagnostic/{d["seed"]}/{f}'] for f in TARGET_DESCRIPTIONS}
        suite_check(d['target_results'],hashes); suite_check(d['parent_targets'],hashes)
        rows=measured_rows(ap['forecast'],d['behavior'],d['target_results'],d['parent_targets'],protocol['epsilon'])
        require(equal(rows,d['rows']) and equal(metrics(rows),d['metrics']),'diagnostic_metric_mismatch')
        require(equal(after[0]['payload'],{k:v for k,v in d.items() if k!='journal_integrity'}),'diagnostic_result_mismatch')
    panel_complete=[e for e in study if e['kind']=='common_code_panel_complete']
    require(len(panel_complete)==1 and panel_complete[0]['payload']=={'rows':len(diagnostics),'hash':digest(diagnostics)},'diagnostic_terminal_mismatch')
    require(freeze[0]['sequence']<panel_complete[0]['sequence']<min(e['sequence'] for e in held),'diagnostic_stage_order_mismatch')
    require(len(summary['paired_results'])==3,'contrast_count_mismatch')
    for contrast in summary['paired_results']:
        require(not contrast['missing_seeds'] and [p['seed'] for p in contrast['pairs']]==protocol['seeds'],'paired_seed_mismatch')
        for item in contrast['pairs']:
            a,b=(cells[(item['seed'],contrast[key])] for key in ('control','treatment'))
            x,y=a['heldout']['incumbent']['objective'],b['heldout']['incumbent']['objective']
            expected_pair={'seed':item['seed'],'quality_auc_delta':b['quality_curve']['auc']-a['quality_curve']['auc'],
                'heldout_relative_gain':(x-y)/max(abs(x),1e-12),
                'behavior_accuracy_delta':b['rq1b_metrics']['behavior_macro_accuracy']-a['rq1b_metrics']['behavior_macro_accuracy'],
                'target_brier_reduction':a['rq1b_metrics']['target_macro_brier']-b['rq1b_metrics']['target_macro_brier']}
            require(equal(item,expected_pair),'paired_metric_mismatch')
        require(equal(contrast['median_auc_delta'],median(x['quality_auc_delta'] for x in contrast['pairs'])) and equal(contrast['median_heldout_gain'],median(x['heldout_relative_gain'] for x in contrast['pairs'])),'paired_median_mismatch')
    terminal=[e for e in study if e['kind']=='study_terminal']
    require(len(terminal)==1 and terminal[0]['payload']['summary_hash']==digest({k:v for k,v in summary.items() if k!='journal_integrity'}),'summary_terminal_hash_mismatch')
    require(len(requests)<=protocol['budget']['http_requests_max_with_two_transport_retries'],'transport_budget_exceeded')
    transport={'http_requests':len(requests),'by_purpose':dict(Counter(r['purpose'] for r in requests)),
        'failed_http':sum(not r['ok'] for r in requests),'retry_http':sum(r.get('transport_attempt',1)>1 for r in requests)+outer_retries,
        'known_input_tokens':sum(r.get('input_tokens') or 0 for r in requests),'known_output_tokens':sum(r.get('output_tokens') or 0 for r in requests),
        'requests_missing_usage':sum(r.get('input_tokens') is None or r.get('output_tokens') is None for r in requests),
        'response_models':dict(Counter(r.get('response_model') or 'missing' for r in requests)),
        'finish_reasons':dict(Counter(r.get('finish_reason') or 'missing' for r in requests)),
        'reasoning_characters':sum(r.get('reasoning_characters',0) for r in requests),
        'summed_request_seconds':round(sum(r.get('elapsed_seconds',0) for r in requests),3)}
    return {'status':'evidence_integrity_verified','study_status':summary['status'],'protocol_hash':protocol['protocol_hash'],
        'source_integrity':source,'source_commit':protocol['execution_head'],'summary_sha256':file_hash(run_dir/'summary.json'),
        'expected_cells':protocol['expected_cells'],'returned_cells':len(cells),'expected_diagnostic_rows':protocol['expected_diagnostic_rows'],
        'returned_diagnostic_rows':len(diagnostics),'cells':cell_checks,'transport':transport,'heldout_after_global_freeze':True,
        'exact_feedback_context_reconstructed':True,'analyst_prompt_reconstructed':True,'labels_and_auc_recalculated':True,
        'all_strict_trace_conditions_recalculated':True,'scientific_claim_allowed':summary['scientific_claim_allowed'],
        'boundary':'Read-only internal consistency audit. Metric aggregation reuses frozen metrics(); labels and AUC separately reconstructed. Does not reexecute programs, recover raw provider responses, verify stochastic correctness or prove causal mediation. Generation context and request hashes checked; full EOH generation prompt not reconstructed because separate algorithm descriptions are not journaled.'}

def audit_partial(run_dir):
    """Preserve a failed cohort as incomplete; never promote its partial endpoints."""
    summary,protocol=read(run_dir/'summary.json'),read(run_dir/'protocol_frozen.json')
    require(summary['status']=='incomplete' and not summary['scientific_claim_allowed'],'not_an_incomplete_run')
    require(digest({k:v for k,v in protocol.items() if k!='protocol_hash'})==protocol['protocol_hash'],'protocol_hash_mismatch')
    source={n:(ROOT/n).is_file() and file_hash(ROOT/n)==h for n,h in protocol['source_hashes'].items()}
    require(all(source.values()),'frozen_source_mismatch')
    study=records(run_dir/'events.jsonl',protocol)
    require(equal(study[0]['payload'],protocol),'initial_protocol_mismatch')
    terminal=[e for e in study if e['kind']=='study_terminal']
    require(len(terminal)==1 and terminal[0]['payload']['summary_hash']==digest({k:v for k,v in summary.items() if k!='journal_integrity'}),'terminal_summary_mismatch')
    require(not any(e['kind'] in {'heldout_evaluation','all_incumbents_frozen','common_code_panel_complete'} for e in study),'unexpected_stage_in_partial_run')
    require(not (run_dir/'diagnostic').exists(),'unexpected_diagnostic_directory')
    requests=[e['payload'] for e in study if e['kind']=='model_request']; cells=[]; failure_receipts=[]
    spec=get_problem_spec('cvrp_construct'); baseline_id=digest(spec['baseline_code']); total_rows=0
    for seed in protocol['seeds']:
        for arm in protocol['arms']:
            cid=f'cvrp_construct/{seed}/{arm["id"]}'; path=run_dir/'cells'/cid/'events.jsonl'
            if not path.exists():
                cells.append({'cell_id':cid,'seed':seed,'arm':arm['id'],'status':'not_started','evaluated_slots':0,'started_slots':0,'requests':0,'failed_requests':0})
                continue
            stream=records(path,protocol,check_v2=False); local=[e['payload'] for e in stream if e['kind']=='model_request']; requests.extend(local)
            if protocol.get('execution_version')==2:
                _verify_v2_recovery(stream,protocol,path.parent/'checkpoints',allow_terminal_failure=True)
            reqstarts=[e['payload'] for e in stream if e['kind']=='model_request_started']
            require(len(reqstarts)==len(local) and all(all(x[k]==y[k] for k in ('model','purpose','prompt_hash','transport_attempt')) for x,y in zip(reqstarts,local)),'request_receipt_mismatch')
            pending_analysis={}; targets={}; outcomes={'behavior':[],'targeted':[]}; seen_analysis=set(); count=0; initial=best=None; points=[[0,0.0]]
            for e in stream:
                k,p=e['kind'],e['payload']
                if k=='external_teacher_baseline': initial=best=p['dev_train']['objective']
                elif k=='external_teacher_target_baseline': targets[baseline_id]=p
                elif k=='feedback_exposure': require(digest(p['generation_context'])==p['context_hash'] and (arm['id']!='scalar' or not p['included_forecast']),'feedback_integrity_mismatch')
                elif k=='prospective_analysis':
                    panel_check(p['panel'],protocol['panel_hashes'][f'{seed}/{count+1}']); pending_analysis[p['analysis_id']]=e
                    require(p['analysis_id'] not in seen_analysis,'duplicate_analysis_id'); seen_analysis.add(p['analysis_id'])
                    forecast_check(p['forecast'],p['panel'])
                elif k in {'candidate_evaluation','candidate_attempt_failure'}:
                    count+=1; require(p['attempt']==count,'attempt_sequence_mismatch')
                    if k=='candidate_attempt_failure': rows=failed_rows(build_probe_panel(seed,count))
                    else:
                        ap=pending_analysis[p['analysis_id']]; require(ap['sequence']<e['sequence'] and ap['content_hash']==p['analysis_event_hash'],'prospective_order_mismatch')
                        ap=ap['payload']; parent=targets[ap['parent_candidate_ids'][0]]
                        cp=(path.parent/p['code_path']).resolve(); require(cp.is_relative_to(path.parent.resolve()) and digest(cp.read_text(encoding='utf-8'))==p['candidate_id'],'candidate_file_mismatch')
                        require(p['behavior']['panel_hash']==ap['panel']['content_hash'] and digest(parent)==p['parent_target_results_hash'],'measurement_identity_mismatch')
                        rows=measured_rows(ap['forecast'],p['behavior'],p['target_results'],parent,protocol['epsilon'])
                        if p['valid']:
                            targets.setdefault(p['candidate_id'],p['target_results']); best=min(best,p['results']['dev_train']['objective'])
                    require(equal(rows,p['measurement_rows']),'partial_measurement_recalculation_mismatch')
                    for key in outcomes: outcomes[key].extend(rows[key])
                    points.append([count,(initial-best)/max(abs(initial),1e-12)])
            freeze=[e for e in stream if e['kind']=='cell_frozen']; endpoints=[e for e in stream if e['kind']=='rq1b_cell_endpoints']
            if freeze:
                require(count==protocol['candidate_attempts'] and len(freeze)==len(endpoints)==1,'incomplete_cell_freeze')
                curve={'initial_objective':initial,'points':points,'auc':sum(x[1] for x in points[:-1])/protocol['candidate_attempts']}
                require(equal(curve,freeze[0]['payload']['quality_curve']),'partial_frozen_auc_mismatch')
                require(equal(metrics(outcomes),endpoints[0]['payload']['rq1b_metrics']),'partial_endpoint_mismatch')
            require(len(outcomes['behavior'])==6*count and len(outcomes['targeted'])==3*count,'partial_denominator_mismatch'); total_rows+=count
            for r in local:
                if not r['ok']: failure_receipts.append({'cell_id':cid,**{k:r.get(k) for k in ('purpose','http_status','error_code','transport_attempt','elapsed_seconds')}})
            cells.append({'cell_id':cid,'seed':seed,'arm':arm['id'],'status':'cell_frozen' if freeze else 'interrupted',
                'evaluated_slots':count,'started_slots':sum(e['kind']=='action_started' for e in stream),
                'requests':len(local),'failed_requests':sum(not r['ok'] for r in local),
                'journal_terminal_hash':verify_journal(path)['terminal_hash']})
    transport={'http_requests':len(requests),'by_purpose':dict(Counter(r['purpose'] for r in requests)),
        'failed_http':sum(not r['ok'] for r in requests),'retry_http':sum(r.get('transport_attempt',1)>1 for r in requests),
        'known_input_tokens':sum(r.get('input_tokens') or 0 for r in requests),'known_output_tokens':sum(r.get('output_tokens') or 0 for r in requests),
        'requests_missing_usage':sum(r.get('input_tokens') is None or r.get('output_tokens') is None for r in requests)}
    return {'status':'partial_integrity_verified','study_status':'incomplete','scientific_claim_allowed':False,
        'protocol_hash':protocol['protocol_hash'],'source_commit':protocol['execution_head'],'source_integrity':source,
        'summary_sha256':file_hash(run_dir/'summary.json'),'wall_time_seconds':summary['wall_time_seconds'],
        'summary_returned_cells':summary['completed_cells'],'locally_frozen_cells':sum(c['status']=='cell_frozen' for c in cells),
        'interrupted_cells':sum(c['status']=='interrupted' for c in cells),'not_started_cells':sum(c['status']=='not_started' for c in cells),
        'evaluated_slots':total_rows,'started_slots':sum(c['started_slots'] for c in cells),'planned_candidate_slots':protocol['budget']['candidate_slots'],
        'diagnostic_rows':0,'heldout_evaluations':0,'cells':cells,'transport':transport,'failure_receipts':failure_receipts,
        'execution_version':protocol.get('execution_version',1),
        'durable_checkpoints_verified':protocol.get('execution_version')==2,
        'raw_evidence_directory':'outputs/fme_pilot/'+run_dir.name,
        'boundary':'Partial journal/code/panel/label integrity and complete-cell endpoint recalculation only. No paired effect claim, gate verdict, heldout result or full-cohort causal/lineage validation. '+('v2 successful-response checkpoints and terminal interrupted state verified; no automatic response replay or resume has been executed.' if protocol.get('execution_version')==2 else 'Summary collector loses later completed batch members after first exception; local frozen records retained separately without rewriting historical summary.')}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir',type=Path); parser.add_argument('--output',type=Path); parser.add_argument('--partial',action='store_true')
    args=parser.parse_args(); result=(audit_partial if args.partial else audit)(args.run_dir.resolve())
    text=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(text,encoding='utf-8')
    print(text)
