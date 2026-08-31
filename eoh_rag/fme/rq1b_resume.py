"""Strict historical replay gate and transport-only continuation of RQ1b-v2.

Historical evaluator receipts are replayed, not recomputed or improved. New
evaluations and all scientific methods remain the unchanged frozen adapters.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import random
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from eoh_rag.fme import rq1b as science
from eoh_rag.fme.online_adapters import ROOT, EvidenceJournal, ProviderFailure, digest, file_hash, verify_journal
from eoh_rag.fme.rq1b_v2 import DurableCell, atomic_json, safe_error
from eoh_rag.fme.rq1b_transport import read_checkpoint
from eoh_rag.fme.rq1b_resume_transport import RemainingTransport

CONTRACT=ROOT/'agent_records/contracts/refactor0830_rq1b_v2_resume_v1.json'
TRANSPORT_EVENTS={'recovery_started','transport_retry_scheduled','model_request_started','model_request','checkpoint_saved'}

class ConsistencyError(RuntimeError): pass

def need(value, message):
    if not value: raise ConsistencyError(message)

def read(path): return json.loads(path.read_text(encoding='utf-8'))

def events(path):
    verify_journal(path)
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]

def tree_hashes(directory):
    return {p.relative_to(directory).as_posix():file_hash(p) for p in sorted(directory.rglob('*')) if p.is_file()}

class ReplayJournal(EvidenceJournal):
    def __init__(self, base, original, rows):
        self.__dict__.update(base.__dict__)
        self.original=original; self.rows=rows; self.cursor=0

    def append(self,kind,payload):
        expected=self.rows[self.cursor] if self.cursor<len(self.rows) else None
        if expected:
            need(expected['kind']==kind, f'event_kind_mismatch:{self.cursor+1}:{kind}:{expected["kind"]}')
            need(digest(payload)==digest(expected['payload']),f'event_payload_mismatch:{self.cursor+1}:{kind}')
        result=super().append(kind,payload)
        if expected:
            need(result==expected['content_hash'],f'event_hash_mismatch:{self.cursor+1}:{kind}')
            self.cursor+=1
        return result

    def emit_original(self):
        row=self.rows[self.cursor]
        self.append(row['kind'],row['payload'])
        return row

    def save_candidate(self,candidate_id,code):
        if self.cursor<len(self.rows):
            old=self.original/'candidates'/f'{candidate_id}.py'
            need(old.is_file() and old.read_text(encoding='utf-8')==code,'replayed_candidate_code_mismatch')
        return super().save_candidate(candidate_id,code)

class Budget:
    def __init__(self,protocol,original,journal):
        self.protocol=protocol; self.original=original; self.journal=journal
        self.lock=threading.Lock(); self.enabled=False; self.aborted=False; self.entries={}; self.http=0
        for path in sorted(original.rglob('events.jsonl')):
            key=path.parent.relative_to(original).as_posix(); ordinal=0; current=None
            for e in events(path):
                p=e['payload']
                if e['kind']=='recovery_started' and p['cycle']==1:
                    ordinal+=1; current=f'{key}#{ordinal}'
                    self.entries[current]={'attempts':0,'success':False,'model':p['model'],'purpose':p['purpose'],'problem':p['problem'],'prompt_hash':p['prompt_hash']}
                elif e['kind']=='model_request':
                    need(current is not None,'historical_request_without_identity')
                    row=self.entries[current]; row['attempts']+=1; row['success']=p['ok']; self.http+=1
                elif e['kind']=='checkpoint_saved':
                    cp=read_checkpoint(path.parent/'checkpoints'/p['path'],path.parent/'checkpoints')
                    need(cp['protocol_hash']==protocol['protocol_hash'] and cp['response_hash']==p['response_hash'],'historical_checkpoint_identity_mismatch')
        need(self.http==337 and sum(r['success'] for r in self.entries.values())==333,'original_budget_receipt_mismatch')

    def reserve(self,p):
        with self.lock:
            need(self.enabled and not self.aborted,'global_consistency_gate_closed')
            identity={k:p[k] for k in ('model','purpose','problem','prompt_hash')}
            key=p['logical_id']
            if key not in self.entries:
                need(len(self.entries)<self.protocol['budget']['logical_requests_max'],'logical_budget_exhausted')
                self.entries[key]={**identity,'attempts':0,'success':False}
            row=self.entries[key]
            need(not row['success'] and all(row[k]==v for k,v in identity.items()),'request_identity_or_success_reuse_mismatch')
            need(p['global_attempt']==row['attempts']+1<=9,'per_request_http_budget_mismatch')
            need(self.http<self.protocol['budget']['http_requests_max_with_two_transport_retries'],'total_http_budget_exhausted')
            row['attempts']+=1; self.http+=1
            self.journal.append('new_http_reserved',{**p,'cumulative_http':self.http,'logical_requests':len(self.entries)})

    def success(self,key):
        with self.lock: self.entries[key]['success']=True

class ReplayTransport(RemainingTransport):
    def __init__(self,p,journal,budget,key,verify_only=False):
        super().__init__(p,journal,before_request=budget.reserve)
        self.budget=budget; self.key=key; self.logical_cursor=0; self.verify_only=verify_only

    def request(self,prompt,*,purpose,problem):
        self.logical_cursor+=1; logical_id=f'{self.key}#{self.logical_cursor}'
        self.set_logical_id(logical_id)
        prior=0; j=self.journal
        while isinstance(j,ReplayJournal) and j.cursor<len(j.rows) and j.rows[j.cursor]['kind'] in TRANSPORT_EVENTS:
            event=j.rows[j.cursor]; p=event['payload']
            if 'prompt_hash' in p: need(p['prompt_hash']==digest(prompt),'replayed_prompt_hash_mismatch:'+logical_id)
            if 'purpose' in p: need(p['purpose']==purpose and p['model']==self.model,'replayed_request_identity_mismatch')
            if event['kind']=='model_request': self.usage.append(copy.deepcopy(p)); prior+=1
            if event['kind']=='checkpoint_saved':
                old=j.original/'checkpoints'/p['path']; cp=read_checkpoint(old,old.parent)
                need(cp['prompt']==prompt and cp['request_spec']==self._request_spec(prompt,purpose,problem),'replayed_full_prompt_or_spec_mismatch')
                shutil.copyfile(old,self.checkpoint_root/old.name)
                self._ordinal=cp['ordinal']+1; j.emit_original()
                return cp['response']
            j.emit_original()
        if self.verify_only:
            need(prior>0 and not self.usage[-1]['ok'],'replay_missing_historical_response')
            raise ProviderFailure('provider_connectivity_or_protocol_error',retryable=False)
        need(self.budget.enabled and not self.budget.aborted,'api_before_global_consistency_gate')
        result=self.request_remaining(prompt,purpose=purpose,problem=problem,prior_http_attempts=prior)
        self.budget.success(logical_id)
        return result

class ReplayEvaluator:
    def __init__(self,real,rows,budget): self.real=real; self.rows=rows; self.cursor=0; self.budget=budget
    def evaluate(self,problem,code,suite):
        if self.cursor<len(self.rows):
            candidate_id,suite_hash,result=self.rows[self.cursor]
            need(problem=='cvrp_construct' and digest(code)==candidate_id and suite['content_hash']==suite_hash,'cached_evaluation_identity_mismatch')
            self.cursor+=1; return copy.deepcopy(result)
        need(self.budget.enabled and not self.budget.aborted,'historical_evaluation_cache_exhausted_before_gate')
        return self.real.evaluate(problem,code,suite)

class ReplayCell(DurableCell):
    def __init__(self,p,arm,seed,directory,original,budget,verify_only=False):
        super().__init__(p,arm,seed,directory)
        old_rows=events(original/'events.jsonl') if original.exists() else []
        rows=old_rows
        if old_rows and not verify_only and old_rows[-1]['kind']=='action_aborted':
            stop=max(i for i,e in enumerate(old_rows) if e['kind']=='model_request')
            rows=old_rows[:stop+1]
        self.journal=ReplayJournal(self.journal,original,rows)
        self.transport=ReplayTransport(p,self.journal,budget,f'cells/cvrp_construct/{seed}/{arm["id"]}',verify_only)
        self.generator.transport=self.transport; self.budget=budget
        baseline_id=digest(self.spec['baseline_code']); calls=[]; self.behavior_rows=[]; self.behavior_cursor=0
        for e in old_rows:
            item=e['payload']
            if e['kind'] in {'external_teacher_baseline','external_teacher_target_baseline'}:
                calls.extend((baseline_id,r['suite_hash'],r) for r in item.values())
            elif e['kind']=='candidate_evaluation':
                calls.extend((item['candidate_id'],r['suite_hash'],r) for r in item['results'].values())
                calls.extend((item['candidate_id'],r['suite_hash'],r) for r in item['target_results'].values())
                self.behavior_rows.append((item['candidate_id'],item['behavior']['panel_hash'],item['behavior']))
            elif e['kind']=='descendant_trace':
                trace=item['trace']; self.behavior_rows.append((trace['child_id'],trace['source_panel_hash'],item['child_behavior_on_source_panel']))
        self.evaluator=ReplayEvaluator(self.evaluator,calls,budget)

    def behavior(self,code,panel):
        if self.behavior_cursor<len(self.behavior_rows):
            candidate_id,panel_hash,result=self.behavior_rows[self.behavior_cursor]
            need(digest(code)==candidate_id and panel['content_hash']==panel_hash,'cached_behavior_identity_mismatch')
            self.behavior_cursor+=1; self.behavior_worker_calls+=1
            return copy.deepcopy(result)
        need(self.budget.enabled and not self.budget.aborted,'historical_behavior_cache_exhausted_before_gate')
        return super().behavior(code,panel)

    def historical_consumed(self):
        need(self.journal.cursor==len(self.journal.rows),'historical_events_unconsumed')
        need(self.evaluator.cursor==len(self.evaluator.rows) and self.behavior_cursor==len(self.behavior_rows),'historical_evaluation_receipts_unconsumed')

def precheck(protocol,original,directory,budget,summary):
    results=[]; by_id={c['cell_id']:c for c in summary['cells']}
    for path in sorted((original/'cells').glob('*/*/*/events.jsonl')):
        seed=int(path.parent.parent.name); arm=next(a for a in protocol['arms'] if a['id']==path.parent.name)
        cid=f'cvrp_construct/{seed}/{arm["id"]}'
        cell=ReplayCell(protocol,arm,seed,directory/'checks'/'cells'/cid,path.parent,budget,True)
        outcome=None; interrupted=False
        try: outcome=cell.run()
        except ProviderFailure as exc:
            need(cid not in by_id and exc.error_code=='provider_connectivity_or_protocol_error' and not exc.retryable,'replayed_failure_type_mismatch')
            interrupted=True
        cell.historical_consumed()
        need(file_hash(cell.journal.path)==file_hash(path),'complete_historical_journal_bytes_mismatch:'+cid)
        need(read(cell.journal.directory/'cell_checkpoint.json')==read(path.parent/'cell_checkpoint.json'),'final_state_or_lineage_checkpoint_mismatch:'+cid)
        if not interrupted: need(digest(outcome)==digest(by_id[cid]),'complete_cell_result_mismatch:'+cid)
        results.append({'cell_id':cid,'interrupted':interrupted,'journal_hash':file_hash(path),
            'checkpoint_hash':file_hash(path.parent/'cell_checkpoint.json'),'prompt_state_lineage_hash':'exact_match'})
        print(json.dumps({'event':'historical_cell_verified','cell_id':cid,'verified':len(results),'expected':12}),flush=True)
    need(len(results)==12 and sum(r['interrupted'] for r in results)==2,'historical_coordinate_count_mismatch')
    return results

def diagnostic_one(p,directory,seed,name,style,budget):
    # Same frozen diagnostic operations; only its transport is substituted.
    journal=EvidenceJournal(directory/str(seed)/name/style,actor='research_agent')
    code=science.diagnostic_programs()[name]; spec=science.get_problem_spec('cvrp_construct')
    panel=science.build_probe_panel(seed,0); targets=science.target_suites(p,seed)
    need(panel['content_hash']==p['panel_hashes'][f'diagnostic/{seed}'] and digest(code)==p['diagnostic_program_hashes'][name],'diagnostic_identity_mismatch')
    need(all(s['content_hash']==p['suite_hashes'][f'diagnostic/{seed}/{f}'] for f,s in targets.items()),'diagnostic_suite_mismatch')
    transport=ReplayTransport(p,journal,budget,f'diagnostic/{seed}/{name}/{style}')
    prompt=science.build_analysis_prompt(style,code,json.dumps({'code':spec['baseline_code'],'scope':'external_teacher_reference_not_search_parent'}),panel,science.TARGET_DESCRIPTIONS)
    raw=transport.request(prompt,purpose='analysis',problem='cvrp_construct')
    forecast=science.parse_forecast(raw,panel,science.TARGET_DESCRIPTIONS,code,style)
    journal.append('diagnostic_prospective',{'analysis_id':f'diagnostic-{seed}-{name}-{style}','candidate_id':digest(code),
        'prompt_hash':digest(prompt),'response_hash':digest(raw),'panel':panel,'forecast':forecast,'code_actor':'external_teacher'})
    evaluator=science.SubprocessEvaluator(p['evaluator_timeout_seconds'])
    behavior=science.execute_behavior(code,panel,p['evaluator_timeout_seconds'])
    observed={f:evaluator.evaluate('cvrp_construct',code,s) for f,s in targets.items()}
    parent={f:evaluator.evaluate('cvrp_construct',spec['baseline_code'],s) for f,s in targets.items()}
    need(all(r['valid'] for r in parent.values()),'diagnostic_parent_invalid')
    rows=science.forecast_outcomes(forecast,behavior,observed,parent,p['epsilon'])
    result={'seed':seed,'program':name,'style':style,'candidate_id':digest(code),'forecast_valid':forecast['valid'],
        'metrics':science.metrics(rows),'rows':rows,'behavior':behavior,'target_results':observed,'parent_targets':parent}
    journal.append('diagnostic_evaluation',result); result['journal_integrity']=verify_journal(journal.path)
    return result

def run(original,directory,execute):
    contract=read(CONTRACT); p=read(original/'protocol_frozen.json'); old_summary=read(original/'summary.json')
    need(p['protocol_hash']==contract['original_protocol_hash']==digest({k:v for k,v in p.items() if k!='protocol_hash'}),'original_protocol_hash_mismatch')
    need(old_summary['status']=='incomplete' and not old_summary['scientific_claim_allowed'],'original_not_incomplete')
    need(not directory.exists() and not directory.is_relative_to(original) and not original.is_relative_to(directory),'output_must_be_new_and_separate')
    need(all(file_hash(ROOT/name)==h for name,h in p['source_hashes'].items()),'frozen_scientific_source_mismatch')
    science.load_local_env()
    original_hashes=tree_hashes(original); journal=EvidenceJournal(directory,actor='research_agent')
    journal.append('protocol_frozen',p); atomic_json(directory/'protocol_frozen.json',p)
    source_names=['eoh_rag/fme/rq1b_resume.py','eoh_rag/fme/rq1b_resume_transport.py',CONTRACT.relative_to(ROOT).as_posix()]
    manifest={'schema_version':'rq1b-transport-continuation/v1','original_run':original.relative_to(ROOT).as_posix(),
        'original_protocol_hash':p['protocol_hash'],'original_tree_hashes':original_hashes,
        'execution_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'source_hashes':{n:file_hash(ROOT/n) for n in source_names},'contract':contract,
        'historical_replay_scope':'All original successful responses and exact cached evaluator receipts; copied prefixes are not new HTTP or solver calls.'}
    manifest['content_hash']=digest(manifest); atomic_json(directory/'continuation_manifest.json',manifest)
    ledger_journal=EvidenceJournal(directory/'transport_ledger',actor='research_agent')
    budget=Budget(p,original,ledger_journal); started=time.monotonic(); cells=[]; runtime={}; diagnostics=[]; errors=[]
    try:
        # Reuse original preflight without issuing another model request.
        prefix=events(original/'events.jsonl'); end=next(i for i,e in enumerate(prefix) if e['kind']=='checkpoint_saved')
        journal=ReplayJournal(journal,original,prefix[1:end+1])
        transport=ReplayTransport(p,journal,budget,'.',True)
        transport.request('Reply only OK.',purpose='preflight',problem='none')
        checks=precheck(p,original,directory,budget,old_summary)
        need(tree_hashes(original)==original_hashes,'original_evidence_changed_during_precheck')
        receipt={'status':'passed','new_http_requests':0,'new_solver_calls':0,'cells':checks,
            'successful_responses_reused':333,'original_tree_hash':digest(original_hashes),'continuation_manifest_hash':manifest['content_hash']}
        atomic_json(directory/'consistency_gate.json',receipt); journal.append('global_consistency_gate_passed',receipt)
        print(json.dumps({'event':'global_consistency_gate_passed','historical_cells':12,'new_http':0}),flush=True)
        if not execute:
            atomic_json(directory/'verification_only.json',receipt); return {'status':'verified_not_executed','new_http':0}
        need(all(file_hash(ROOT/n)==h for n,h in {**p['source_hashes'],**manifest['source_hashes']}.items()),'source_changed_before_api')
        budget.enabled=True
        coords=[(seed,arm) for seed in p['seeds'] for arm in p['arms']]; random.Random(310827).shuffle(coords)
        def one(coord):
            seed,arm=coord; cid=f'cvrp_construct/{seed}/{arm["id"]}'
            cell=ReplayCell(p,arm,seed,directory/'cells'/cid,original/'cells'/cid,budget)
            try: result=cell.run(); cell.historical_consumed(); return cell,result
            except ConsistencyError:
                budget.aborted=True; raise
        with ThreadPoolExecutor(max_workers=p['cell_concurrency']) as pool:
            for offset in range(0,len(coords),p['cell_concurrency']):
                submitted={pool.submit(one,c):c for c in coords[offset:offset+p['cell_concurrency']]}
                for future in as_completed(submitted):
                    seed,arm=submitted[future]; cid=f'cvrp_construct/{seed}/{arm["id"]}'
                    try: cell,result=future.result()
                    except Exception as exc:
                        errors.append({'cell_id':cid,**safe_error(exc),'consistency_error':str(exc) if isinstance(exc,ConsistencyError) else None}); continue
                    cells.append(result); runtime[cid]=cell
                    journal.append('cell_completed',{'cell_id':cid,'result_hash':digest(result)})
                    print(json.dumps({'event':'cell_completed','cell_id':cid,'completed':len(cells),'expected':24}),flush=True)
                if errors: break
        need(not errors and len(cells)==p['expected_cells'],'incomplete_search_queue')
        journal.append('all_incumbents_frozen',{c['cell_id']:c['incumbent_id'] for c in cells})
        coordinates=[(s,n,a) for s in p['diagnostic_seeds'] for n in p['diagnostic_program_hashes'] for a in ('passive','behavior_grounded')]
        random.Random(92711).shuffle(coordinates)
        with ThreadPoolExecutor(max_workers=p['cell_concurrency']) as pool:
            submitted=[pool.submit(diagnostic_one,p,directory/'diagnostic',*c,budget) for c in coordinates]
            for future in as_completed(submitted):
                try: diagnostics.append(future.result())
                except Exception as exc: errors.append(safe_error(exc)); budget.aborted=True
                print(json.dumps({'event':'diagnostic_progress','completed':len(diagnostics),'expected':36}),flush=True)
        need(not errors and len(diagnostics)==p['expected_diagnostic_rows'],'incomplete_diagnostic_queue')
        journal.append('common_code_panel_complete',{'rows':len(diagnostics),'hash':digest(diagnostics)})
        for result in cells:
            cell=runtime[result['cell_id']]; suite=science.build_suite('cvrp_construct',cell.seed,'heldout',p['heldout_instances'],p['sizes']['cvrp_construct'])
            need(suite['content_hash']==p['suite_hashes'][f'{cell.seed}/heldout'],'heldout_data_mismatch')
            result['heldout']={'incumbent':cell.evaluator.evaluate(cell.problem,cell.population[0]['code'],suite),
                'baseline':cell.evaluator.evaluate(cell.problem,cell.spec['baseline_code'],suite)}
            result['heldout_valid']=all(r['valid'] for r in result['heldout'].values())
            journal.append('heldout_evaluation',{'cell_id':result['cell_id'],'incumbent_id':result['incumbent_id'],'results':result['heldout']})
    except Exception as exc:
        budget.aborted=True; error={**safe_error(exc),'consistency_error':str(exc) if isinstance(exc,ConsistencyError) else None}; errors.append(error)
        # Root journal no longer has an expected scientific replay prefix here.
        if isinstance(journal,ReplayJournal): journal.rows=journal.rows[:journal.cursor]
        journal.append('continuation_stopped',error)
    unchanged=tree_hashes(original)==original_hashes
    source={n:file_hash(ROOT/n)==h for n,h in {**p['source_hashes'],**manifest['source_hashes']}.items()}
    complete=not errors and unchanged and all(source.values()) and len(cells)==24 and len(diagnostics)==36 and all(c.get('heldout_valid') for c in cells)
    result={'status':'pilot_completed' if complete else 'incomplete','scientific_claim_allowed':complete,'study_id':p['study_id'],
        'protocol_hash':p['protocol_hash'],'mode':'online','expected_cells':24,'completed_cells':len(cells),'expected_diagnostic_rows':36,
        'completed_diagnostic_rows':len(diagnostics),'cells':cells,'diagnostic':diagnostics,'source_integrity':source,
        'terminal_error':errors or None,'paired_results':science.paired_results(p,cells),'wall_time_seconds':time.monotonic()-started,
        'continuation':{'manifest_hash':manifest['content_hash'],'original_unchanged':unchanged,'original_http':337,
            'new_http':budget.http-337,'cumulative_http':budget.http,'logical_requests':len(budget.entries)}}
    journal.append('study_terminal',{'summary_hash':digest(result),'status':result['status']})
    result['journal_integrity']=verify_journal(journal.path); atomic_json(directory/'summary.json',result)
    atomic_json(directory/'budget_final.json',{'http':budget.http,'logical_requests':budget.entries,'new_http':budget.http-337})
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--original',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True); parser.add_argument('--execute',action='store_true'); args=parser.parse_args()
    result=run(args.original.resolve(),args.output.resolve(),args.execute)
    print(json.dumps({k:result[k] for k in ('status','completed_cells','completed_diagnostic_rows','terminal_error','continuation') if k in result}),flush=True)
    return 0 if result['status'] in {'pilot_completed','verified_not_executed'} else 2

if __name__=='__main__': raise SystemExit(main())
