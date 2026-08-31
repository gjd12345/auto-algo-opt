"""RQ1b independent rerun with durable requests/state and lossless result collection.

The scientific controller, generator, forecasts, evaluators and selection remain
the frozen v1 implementation. This module changes execution durability only.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
import json
import os
from pathlib import Path
import random
import time

from eoh_rag.fme import rq1b as science
from eoh_rag.fme.online_adapters import ROOT, EvidenceJournal, ProviderFailure, digest, file_hash, verify_journal
from eoh_rag.fme.rq1b_transport import DurableTransport


def atomic_json(path, payload):
    temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w',encoding='utf-8') as stream:
        json.dump(payload,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary,path)


def freeze(manifest):
    protocol=science.load_and_freeze(manifest)
    if protocol.get('execution_version')!=2 or protocol['transport_recovery']!={'additional_cycles':2,'delays_seconds':[10,30],'max_http_attempts_per_logical_request':9}:
        raise ValueError('unsupported_rq1b_execution_policy')
    for name in ('eoh_rag/fme/rq1b_v2.py','eoh_rag/fme/rq1b_transport.py'):
        protocol['source_hashes'][name]=file_hash(ROOT/name)
    protocol.pop('protocol_hash')
    protocol['protocol_hash']=digest(protocol)
    return protocol


class DurableCell(science.RQ1bCell):
    def __init__(self,protocol,arm,seed,directory):
        super().__init__(protocol,arm,seed,directory)
        self.transport=DurableTransport(protocol,self.journal)
        self.generator.transport=self.transport
        self.last_synced_state=None

    def persist_state(self,phase):
        # 不是科学反馈：完整断点只保存在 ignored 输出，不送给模型。
        data={'schema_version':'rq1b-cell-checkpoint/v1','protocol_hash':self.protocol['protocol_hash'],
            'cell_id':f'{self.problem}/{self.seed}/{self.arm["id"]}','phase':phase,
            'journal_sequence':self.journal.sequence,'journal_hash':self.journal.previous_hash,
            'population':self.population,'prior':self.prior,'scalar_feedback':self.scalar_feedback,
            'counts':{k:getattr(self,k) for k in ('attempts','failures','valid','solver_calls','behavior_worker_calls','forecast_valid_count')},
            'initial_objective':self.initial_objective,'observations':[asdict(x) for x in self.observations],
            'analysis_outcomes':[asdict(x) for x in self.analysis_outcomes],'rq_outcomes':self.rq_outcomes,
            'lineage':self.lineage,'fme_state':asdict(self.last_synced_state) if self.last_synced_state else None,
            'scope':'dev_only','resume_boundary':'Durable scientific/request state. This run starts fresh; no automatic old-cohort replay.'}
        data['content_hash']=digest(data)
        target=self.journal.directory/'cell_checkpoint.json'
        atomic_json(target,data)
        self.journal.append('cell_checkpoint_saved',{'phase':phase,'attempt':self.attempts,'content_hash':data['content_hash'],
            'path':'cell_checkpoint.json','parent_ids':[p['candidate_id'] for p in self.population[:1]]})

    def start(self):
        state=super().start()
        self.last_synced_state=state; self.persist_state('baseline_ready')
        return state

    def sync_state(self,state):
        state=super().sync_state(state)
        self.last_synced_state=state
        if self.population and 'target_results' in self.population[0]: self.persist_state('tick_synchronized')
        return state

    def generate(self,action):
        try:
            result=super().generate(action)
        except Exception:
            self.persist_state('action_interrupted')
            raise
        self.persist_state('action_complete_before_tick_sync')
        return result


def diagnostic_one(protocol,directory,seed,name,style):
    journal=EvidenceJournal(directory/str(seed)/name/style,actor='research_agent')
    spec=science.get_problem_spec('cvrp_construct'); code=science.diagnostic_programs()[name]
    panel=science.build_probe_panel(seed,0); targets=science.target_suites(protocol,seed)
    if panel['content_hash']!=protocol['panel_hashes'][f'diagnostic/{seed}'] or digest(code)!=protocol['diagnostic_program_hashes'][name]:
        raise ValueError('diagnostic_input_drift')
    if any(s['content_hash']!=protocol['suite_hashes'][f'diagnostic/{seed}/{f}'] for f,s in targets.items()):
        raise ValueError('diagnostic_target_drift')
    transport=DurableTransport(protocol,journal)
    prompt=science.build_analysis_prompt(style,code,json.dumps({'code':spec['baseline_code'],'scope':'external_teacher_reference_not_search_parent'}),panel,science.TARGET_DESCRIPTIONS)
    raw=transport.request(prompt,purpose='analysis',problem='cvrp_construct')
    forecast=science.parse_forecast(raw,panel,science.TARGET_DESCRIPTIONS,code,style)
    journal.append('diagnostic_prospective',{'analysis_id':f'diagnostic-{seed}-{name}-{style}','candidate_id':digest(code),
        'prompt_hash':digest(prompt),'response_hash':digest(raw),'panel':panel,'forecast':forecast,'code_actor':'external_teacher'})
    evaluator=science.SubprocessEvaluator(protocol['evaluator_timeout_seconds'])
    behavior=science.execute_behavior(code,panel,protocol['evaluator_timeout_seconds'])
    observed={f:evaluator.evaluate('cvrp_construct',code,s) for f,s in targets.items()}
    parent={f:evaluator.evaluate('cvrp_construct',spec['baseline_code'],s) for f,s in targets.items()}
    if not all(r['valid'] for r in parent.values()): raise ValueError('diagnostic_parent_invalid')
    rows=science.forecast_outcomes(forecast,behavior,observed,parent,protocol['epsilon'])
    result={'seed':seed,'program':name,'style':style,'candidate_id':digest(code),'forecast_valid':forecast['valid'],
        'metrics':science.metrics(rows),'rows':rows,'behavior':behavior,'target_results':observed,'parent_targets':parent}
    journal.append('diagnostic_evaluation',result)
    result['journal_integrity']=verify_journal(journal.path)
    return result


def safe_error(exc):
    # 不保存异常正文：网络响应或供应商异常可能带敏感字段。
    return {'error_code':exc.error_code if isinstance(exc,ProviderFailure) else type(exc).__name__,
        'retryable':bool(getattr(exc,'retryable',False)),'http_status':getattr(exc,'status',None)}


def run(protocol,directory):
    started=time.monotonic(); journal=EvidenceJournal(directory,actor='research_agent')
    journal.append('protocol_frozen',protocol); atomic_json(directory/'protocol_frozen.json',protocol)
    cells=[]; runtime={}; diagnostics=[]; errors=[]
    try:
        DurableTransport(protocol,journal).request('Reply only OK.',purpose='preflight',problem='none')
        print(json.dumps({'event':'preflight_completed','model':protocol['resolved_model']}),flush=True)
        coords=[(seed,arm) for seed in protocol['seeds'] for arm in protocol['arms']]
        random.Random(310827).shuffle(coords)
        def one(coord):
            seed,arm=coord
            cell=DurableCell(protocol,arm,seed,directory/'cells'/'cvrp_construct'/str(seed)/arm['id'])
            return cell,cell.run()
        # 保留原批次顺序；同批独立回收所有 future，不被第一个异常吞掉其他结果。
        with ThreadPoolExecutor(max_workers=protocol['cell_concurrency']) as pool:
            for offset in range(0,len(coords),protocol['cell_concurrency']):
                submitted={pool.submit(one,c):c for c in coords[offset:offset+protocol['cell_concurrency']]}
                for future in as_completed(submitted):
                    seed,arm=submitted[future]; cid=f'cvrp_construct/{seed}/{arm["id"]}'
                    try: cell,result=future.result()
                    except Exception as exc:
                        error={'cell_id':cid,**safe_error(exc)}; errors.append(error); journal.append('cell_interrupted',error)
                        print(json.dumps({'event':'cell_interrupted',**error}),flush=True)
                        continue
                    cells.append(result); runtime[cid]=cell
                    journal.append('cell_completed',{'cell_id':cid,'result_hash':digest(result)})
                    print(json.dumps({'event':'cell_completed','cell_id':cid,'completed':len(cells),'expected':protocol['expected_cells'],
                        'valid':result['valid_candidates'],'attempts':result['candidate_attempts']}),flush=True)
                if errors: break  # 不因基础设施失败继续扩充已不完整 cohort。
        if errors or len(cells)!=protocol['expected_cells'] or any(c['status']!='completed' for c in cells):
            raise ValueError('incomplete_candidate_budget')
        journal.append('all_incumbents_frozen',{r['cell_id']:r['incumbent_id'] for r in cells})
        coordinates=[(seed,name,style) for seed in protocol['diagnostic_seeds'] for name in protocol['diagnostic_program_hashes'] for style in ('passive','behavior_grounded')]
        random.Random(92711).shuffle(coordinates)
        with ThreadPoolExecutor(max_workers=protocol['cell_concurrency']) as pool:
            submitted={pool.submit(diagnostic_one,protocol,directory/'diagnostic',*c):c for c in coordinates}
            for future in as_completed(submitted):
                try: result=future.result()
                except Exception as exc:
                    error={'diagnostic_coordinate':submitted[future],**safe_error(exc)}; errors.append(error); journal.append('diagnostic_interrupted',error)
                    continue
                diagnostics.append(result)
                print(json.dumps({'event':'common_code_diagnostic','completed':len(diagnostics),'expected':len(coordinates)}),flush=True)
        if errors or len(diagnostics)!=protocol['expected_diagnostic_rows']: raise ValueError('incomplete_diagnostic_budget')
        journal.append('common_code_panel_complete',{'rows':len(diagnostics),'hash':digest(diagnostics)})
        for result in cells:
            cell=runtime[result['cell_id']]
            suite=science.build_suite('cvrp_construct',cell.seed,'heldout',protocol['heldout_instances'],protocol['sizes']['cvrp_construct'])
            if suite['content_hash']!=protocol['suite_hashes'][f'{cell.seed}/heldout']: raise ValueError('heldout_data_drift')
            result['heldout']={'incumbent':cell.evaluator.evaluate(cell.problem,cell.population[0]['code'],suite),
                'baseline':cell.evaluator.evaluate(cell.problem,cell.spec['baseline_code'],suite)}
            result['heldout_valid']=all(r['valid'] for r in result['heldout'].values())
            journal.append('heldout_evaluation',{'cell_id':result['cell_id'],'incumbent_id':result['incumbent_id'],'results':result['heldout']})
    except Exception as exc:
        error=safe_error(exc); errors.append(error); journal.append('study_interrupted',error)
    source_matches={n:file_hash(ROOT/n)==h for n,h in protocol['source_hashes'].items()}
    complete=not errors and len(cells)==protocol['expected_cells'] and len(diagnostics)==protocol['expected_diagnostic_rows'] and all(c.get('heldout_valid') for c in cells) and all(source_matches.values())
    result={'status':'pilot_completed' if complete else 'incomplete','scientific_claim_allowed':complete,
        'study_id':protocol['study_id'],'protocol_hash':protocol['protocol_hash'],'mode':'online',
        'expected_cells':protocol['expected_cells'],'completed_cells':len(cells),
        'expected_diagnostic_rows':protocol['expected_diagnostic_rows'],'completed_diagnostic_rows':len(diagnostics),
        'cells':cells,'diagnostic':diagnostics,'source_integrity':source_matches,'terminal_error':errors or None,
        'paired_results':science.paired_results(protocol,cells),'wall_time_seconds':time.monotonic()-started}
    journal.append('study_terminal',{'summary_hash':digest(result),'status':result['status']})
    result['journal_integrity']=verify_journal(journal.path); atomic_json(directory/'summary.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=ROOT/'eoh_rag_workspace/experiments/manifests/refactor0830_rq1b_v2.json')
    parser.add_argument('--output',type=Path,required=True); parser.add_argument('--execute',action='store_true')
    args=parser.parse_args(); protocol=freeze(args.manifest.resolve())
    if args.execute: result=run(protocol,args.output.resolve())
    else:
        args.output.mkdir(parents=True,exist_ok=False); atomic_json(args.output/'protocol_frozen.json',protocol)
        result={'status':'prepared_not_executed','protocol_hash':protocol['protocol_hash']}
    print(json.dumps({k:result[k] for k in ('status','protocol_hash','completed_cells','completed_diagnostic_rows','terminal_error','wall_time_seconds') if k in result}),flush=True)
    return 0 if result['status'] in {'pilot_completed','prepared_not_executed'} else 2


if __name__=='__main__':
    raise SystemExit(main())
