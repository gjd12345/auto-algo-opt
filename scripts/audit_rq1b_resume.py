"""Read-only original/replay/continuation identity and scientific evidence audit."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from eoh_rag.fme.online_adapters import ROOT,digest,file_hash,verify_journal
from eoh_rag.fme.rq1b_transport import read_checkpoint
from scripts.audit_rq1b import audit as scientific_audit

def need(ok,code):
    if not ok: raise ValueError(code)
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def evs(p):
    verify_journal(p)
    return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines()]
def tree(p): return {x.relative_to(p).as_posix():file_hash(x) for x in sorted(p.rglob('*')) if x.is_file()}

def requests(root):
    entries={}; reservations=[]; receipts=[]
    paths=[root/'events.jsonl',*sorted((root/'cells').glob('*/*/*/events.jsonl')),*sorted((root/'diagnostic').glob('*/*/*/events.jsonl'))]
    for path in paths:
        coordinate=path.parent.relative_to(root).as_posix(); ordinal=0; current=None; reservation=None
        for e in evs(path):
            p=e['payload']
            if e['kind']=='recovery_started' and p['cycle']==1:
                ordinal+=1; current=f'{coordinate}#{ordinal}'
                entries[current]={'attempts':0,'success':False,**{k:p[k] for k in ('model','purpose','problem','prompt_hash')}}
            elif e['kind']=='resume_http_attempt_reserved':
                need(current==p['logical_id'] and reservation is None,'reservation_logical_identity_mismatch')
                reservation=p; reservations.append(p)
            elif e['kind']=='model_request':
                need(current in entries,'http_without_logical_identity'); item=entries[current]
                need(not item['success'],'successful_logical_request_resampled')
                need(all(item[k]==p[k] for k in ('model','purpose','problem','prompt_hash')),'logical_request_shape_changed')
                item['attempts']+=1; item['success']=p['ok']; receipts.append(p)
                need(item['attempts']<=9 and p['transport_attempt']==(item['attempts']-1)%3+1,'per_logical_http_cap_or_sequence')
                if reservation:
                    need(reservation['global_attempt']==item['attempts'] and all(reservation[k]==p[k] for k in ('model','purpose','problem','prompt_hash')),'reservation_http_receipt_mismatch')
            elif e['kind']=='resume_http_attempt_result':
                need(reservation is not None and p['logical_id']==current and p['global_attempt']==reservation['global_attempt'],'resume_result_identity_mismatch')
                need(bool(p['ok'])==bool(entries[current]['success']),'resume_result_receipt_mismatch'); reservation=None
            elif e['kind']=='checkpoint_saved':
                cp=read_checkpoint(path.parent/'checkpoints'/p['path'],path.parent/'checkpoints')
                need(entries[current]['success'] and cp['prompt_hash']==entries[current]['prompt_hash'] and cp['response_hash']==p['response_hash'],'checkpoint_logical_identity_mismatch')
        need(reservation is None,'missing_terminal_http_receipt')
    return entries,reservations,receipts

def audit(run):
    manifest=read(run/'continuation_manifest.json'); original=(ROOT/manifest['original_run']).resolve()
    protocol=read(original/'protocol_frozen.json'); summary=read(run/'summary.json')
    need(summary['status']=='pilot_completed','continuation_not_complete')
    need(original.is_relative_to(ROOT) and original!=run and not original.is_relative_to(run),'invalid_original_directory')
    need(manifest['content_hash']==digest({k:v for k,v in manifest.items() if k!='content_hash'}),'manifest_hash_mismatch')
    need(manifest['original_protocol_hash']==protocol['protocol_hash'] and read(run/'protocol_frozen.json')==protocol,'scientific_protocol_changed')
    need(tree(original)==manifest['original_tree_hashes'],'original_tree_changed')
    source={n:(ROOT/n).is_file() and file_hash(ROOT/n)==h for n,h in manifest['source_hashes'].items()}
    need(all(source.values()),'continuation_source_mismatch')
    need(subprocess.run(['git','cat-file','-e',manifest['execution_commit']+'^{commit}'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0,'execution_commit_missing')
    gate=read(run/'consistency_gate.json')
    need(gate['status']=='passed' and gate['new_http_requests']==gate['new_solver_calls']==0 and gate['successful_responses_reused']==333,'consistency_gate_mismatch')
    need(gate['continuation_manifest_hash']==manifest['content_hash'] and gate['original_tree_hash']==digest(manifest['original_tree_hashes']),'gate_identity_mismatch')
    checks={c['cell_id']:c for c in gate['cells']}; oldcells=sorted((original/'cells').glob('*/*/*/events.jsonl'))
    need(len(checks)==len(gate['cells'])==len(oldcells)==12,'historical_coordinate_count_mismatch')
    for old in oldcells:
        cid=old.parent.relative_to(original/'cells').as_posix(); check=run/'checks'/'cells'/cid; active=run/'cells'/cid
        need(cid in checks and checks[cid]['prompt_state_lineage_hash']=='exact_match','historical_gate_cell_missing')
        need((check/'events.jsonl').read_bytes()==old.read_bytes(),'historical_replay_journal_not_exact')
        need((check/'cell_checkpoint.json').read_bytes()==(old.parent/'cell_checkpoint.json').read_bytes(),'historical_replay_state_not_exact')
        need(checks[cid]['journal_hash']==file_hash(old) and checks[cid]['checkpoint_hash']==file_hash(old.parent/'cell_checkpoint.json'),'historical_gate_receipt_hash_mismatch')
        original_events=evs(old); interrupted=original_events[-1]['kind']=='action_aborted'
        prefix_count=1+max(i for i,e in enumerate(original_events) if e['kind']=='model_request') if interrupted else len(original_events)
        need(evs(active/'events.jsonl')[:prefix_count]==original_events[:prefix_count],'active_historical_prefix_mismatch')
        for cp in (old.parent/'checkpoints').glob('request-*.json'):
            need(file_hash(cp)==file_hash(active/'checkpoints'/cp.name),'successful_response_not_reused_exactly')
    old_entries,_,old_http=requests(original); entries,resumes,http=requests(run)
    need(len(old_http)==337 and sum(r['success'] for r in old_entries.values())==333,'original_budget_mismatch')
    need(len(entries)<=805 and len(http)<=7245,'total_budget_exceeded')
    for key,old in old_entries.items():
        need(key in entries and all(entries[key][k]==old[k] for k in ('model','purpose','problem','prompt_hash')),'original_logical_request_changed')
        if old['success']: need(entries[key]==old,'successful_request_resampled')
    ledger=evs(run/'transport_ledger/events.jsonl'); reservations=[e['payload'] for e in ledger if e['kind']=='new_http_reserved']
    stripped=[{k:v for k,v in p.items() if k not in {'cumulative_http','logical_requests'}} for p in reservations]
    need(Counter(map(digest,stripped))==Counter(map(digest,resumes)),'reservation_ledger_mismatch')
    running={k:dict(v) for k,v in old_entries.items()}; running_http=337
    for p in reservations:
        key=p['logical_id']; old=old_entries.get(key)
        need(p['old_attempts']==(old['attempts'] if old else 0),'old_failed_attempts_not_counted')
        need(not old or not old['success'],'new_http_for_successful_original_request')
        if key not in running: running[key]={'attempts':0}
        running[key]['attempts']+=1; running_http+=1
        need(p['global_attempt']==running[key]['attempts']<=9,'global_attempt_budget_mismatch')
        need(p['cumulative_http']==running_http and p['logical_requests']==len(running),'cumulative_budget_ledger_mismatch')
    need(len(http)==337+len(reservations)==running_http,'replay_http_double_counted_or_lost')
    budget=read(run/'budget_final.json')
    need(budget=={'http':len(http),'logical_requests':entries,'new_http':len(reservations)},'final_budget_state_mismatch')
    need(all(c['success'] for c in entries.values()),'uncompleted_logical_request_in_complete_run')
    root_events=evs(run/'events.jsonl'); gates=[e for e in root_events if e['kind']=='global_consistency_gate_passed']
    need(len(gates)==1 and gates[0]['payload']==gate,'global_gate_event_mismatch')
    need(summary['continuation']=={'manifest_hash':manifest['content_hash'],'original_unchanged':True,'original_http':337,'new_http':len(reservations),'cumulative_http':len(http),'logical_requests':len(entries)},'summary_continuation_mismatch')
    scientific=scientific_audit(run,allow_stream_json=True)
    need(scientific['transport']['http_requests']==len(http),'scientific_transport_count_mismatch')
    scientific['source_integrity'].update(source)
    scientific['continuation_audit']={'status':'resume_integrity_verified','original_unchanged':True,
        'manifest_hash':manifest['content_hash'],'execution_commit':manifest['execution_commit'],
        'historical_replay_cells':12,'successful_responses_reused':333,'pre_api_gate_exact':True,
        'original_http':337,'new_http':len(reservations),'cumulative_http':len(http),'logical_requests':len(entries),
        'every_logical_http_at_most9':True,'original_wall_time_seconds':read(original/'summary.json')['wall_time_seconds']}
    scientific['boundary']='Read-only internal consistency audit; no provider or solver execution. Labels and AUC reconstructed; frozen metrics() reused for aggregates. This continuation additionally verifies exact historical replay journals and complete state checkpoints for all12 original cells, including full prompt/state/lineage identity checked by the pre-API frozen replay gate. New request checkpoint prompt/spec hashes and HTTP ledgers checked; new generation prompts are not independently regenerated by this post-run auditor. Not a proof of stochastic correctness or causal mediation.'
    return scientific

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('run_dir',type=Path); ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args(); result=audit(a.run_dir.resolve()); a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'status':result['status'],'continuation_audit':result['continuation_audit'],'transport':result['transport']},ensure_ascii=False))
