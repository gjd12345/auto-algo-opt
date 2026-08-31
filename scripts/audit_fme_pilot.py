"""Read-only audit of a terminal FME pilot's actual journals, candidates and heldout gate."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eoh_rag.fme.online_adapters import digest, verify_journal
from eoh_rag.fme.potential import AnalysisOutcome, QualityObservation, analysis_potential_metrics, quality_potential_curve
from eoh_rag.fme.online_pilot import summarize_contrasts


def records(path):
    verify_journal(path)
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def verify_transport_retries(events, maximum_retries):
    previous=None
    scheduled=None
    for event in events:
        kind,payload=event['kind'],event['payload']
        if kind=='model_request':
            attempt=payload.get('transport_attempt',1)
            require(1<=attempt<=maximum_retries+1, 'transport_attempt_budget_exceeded')
            if attempt>1:
                require(previous and not previous['ok'] and scheduled, 'retry_without_failed_request')
                require(previous.get('transport_attempt',1)+1==attempt, 'nonsequential_transport_retry')
                require(all(payload[key]==previous[key]==scheduled[key] for key in ('model','purpose','prompt_hash')), 'retry_request_changed')
                require(scheduled['failed_transport_attempt']==attempt-1 and scheduled['delay_seconds']==2**(attempt-1), 'retry_schedule_mismatch')
            previous=payload
            scheduled=None
        elif kind=='transport_retry_scheduled':
            require(previous and not previous['ok'], 'retry_after_success')
            scheduled=payload


def require(condition, code):
    if not condition:
        raise ValueError(code)


def audit(directory):
    summary=json.loads((directory/'summary.json').read_text(encoding='utf-8'))
    protocol=json.loads((directory/'protocol_frozen.json').read_text(encoding='utf-8'))
    require(digest({k:v for k,v in protocol.items() if k!='protocol_hash'})==protocol['protocol_hash'], 'protocol_hash_mismatch')
    study=records(directory/'events.jsonl')
    verify_transport_retries(study,protocol.get('network_retries',0))
    require(study[0]['kind']=='protocol_frozen', 'missing_initial_protocol')
    if summary['status'] in {'blocked_before_cohort','preflight_ready'}:
        require(not list(directory.glob('cells/*/*/*')), 'preflight_created_experiment_cells')
        return {'status':'verified_preflight_only','scientific_claim_allowed':False}
    terminal=[r for r in study if r['kind']=='study_terminal']
    require(len(terminal)==1 and terminal[0]['payload']['summary_hash']==digest({k:v for k,v in summary.items() if k!='journal_integrity'}), 'terminal_summary_hash_mismatch')
    actions=Counter()
    requests=[]
    valid=attempts=admitted=prospective=0
    cells_by_id={cell['cell_id']:cell for cell in summary['cells']}
    for journal in directory.glob('cells/*/*/*/events.jsonl'):
        events=records(journal)
        verify_transport_retries(events,protocol.get('network_retries',0))
        cell_id='/'.join(journal.parent.relative_to(directory/'cells').parts)
        row=cells_by_id.get(cell_id)
        rejected_ids=set()
        admitted_ids=set()
        predictions={}
        objective_by_candidate={}
        initial=None
        best=None
        local_attempts=0
        observations=[]
        outcomes=[]
        for event in events:
            kind,payload=event['kind'],event['payload']
            if kind=='model_request': requests.append(payload)
            if kind=='external_teacher_baseline':
                initial=best=payload['dev_train']['objective']
            if kind=='algorithm_admission':
                objective_by_candidate[payload['profile']['candidate_id']]=payload['evaluation']['objective']
            if kind=='prospective_analysis':
                prospective+=1
                predictions[payload['analysis_id']]=payload
            if kind=='action_started':
                actions[payload['action']]+=1
                if payload['action'] in {'invent_algorithm','repair_failed_mechanism','transfer_abstract_mechanism'}:
                    attempts+=1
                    local_attempts+=1
            if kind=='candidate_evaluation':
                valid+=int(payload['valid'])
                candidate=journal.parent/payload['code_path']
                require(candidate.resolve().is_relative_to(journal.parent.resolve()), 'candidate_path_outside_cell')
                require(digest(candidate.read_text(encoding='utf-8'))==payload['candidate_id'], 'candidate_hash_mismatch')
                if payload['valid']:
                    prediction=predictions[payload['analysis_id']]
                    parent=objective_by_candidate[prediction['parent_candidate_ids'][0]]
                    value=payload['results']['dev_train']['objective']
                    actual=(parent-value)/max(abs(parent),1e-12)
                    outcomes.append(AnalysisOutcome(prediction['analysis_id'],prediction['predicted_effect'],prediction['predicted_success_probability'],actual))
                    best=min(best,value)
                    objective_by_candidate[payload['candidate_id']]=value
            if kind=='action_finished' and payload['action'] in {'invent_algorithm','repair_failed_mechanism','transfer_abstract_mechanism'}:
                observations.append(QualityObservation(local_attempts,best))
            if kind=='counterexample_selection' and 'artifact' in payload:
                identity=payload['artifact']['counterexample_id']
                if payload['admitted']:
                    require(payload['admission']['admitted'] and payload['regression']>1e-12, 'unjustified_counterexample_admission')
                    require(payload['validity']['domain_validity_status']=='valid', 'out_of_domain_counterexample')
                    admitted_ids.add(identity)
                    admitted+=1
                else:
                    rejected_ids.add(identity)
            if kind=='counterexample_comparison':
                require(payload['counterexample_id'] in admitted_ids, 'comparison_without_admitted_counterexample')
                require(payload['strong_id']!=payload['comparator_id'], 'self_comparison')
            if kind=='cell_frozen':
                require(row is not None, 'frozen_cell_missing_from_summary')
                require(payload['incumbent_id']==row['incumbent_id'], 'incumbent_changed_after_freeze')
                require(row['candidate_attempts']<=protocol['candidate_attempts'], 'candidate_budget_exceeded')
                require(row['candidate_attempts']==local_attempts, 'attempt_count_mismatch')
                require(best==row['final_objective'], 'incumbent_objective_mismatch')
                if observations:
                    curve=quality_potential_curve(initial_objective=initial,observations=observations,maximum_budget=protocol['candidate_attempts'],integration='step')
                    require(digest(asdict(curve))==digest(row['quality_curve']), 'quality_curve_recalculation_mismatch')
                metrics=analysis_potential_metrics(outcomes) if outcomes else None
                require(digest(metrics)==digest(row['analysis_metrics']), 'analysis_metrics_recalculation_mismatch')
                require(set(c['counterexample_id'] for c in row['archives']['counterexamples'])==admitted_ids, 'counterexample_archive_mismatch')
                require(not ((rejected_ids-admitted_ids)&{c['counterexample_id'] for c in row['archives']['counterexamples']}), 'rejected_counterexample_counted')
                if row['status']=='completed' and row['candidate_attempts']<protocol['candidate_attempts']:
                    require(row.get('planned_early_stop') and row['stop_reason'] in protocol.get('planned_early_stop_reasons',[]), 'unregistered_early_stop')
    freeze=[r for r in study if r['kind']=='all_incumbents_frozen']
    heldout=[r for r in study if r['kind']=='heldout_evaluation']
    expected=len(protocol['problems'])*len(protocol['seeds'])*len(protocol['arms'])
    if heldout:
        require(len(freeze)==1 and len(cells_by_id)==expected, 'heldout_unsealed_before_complete_cohort')
        require(len(freeze[0]['payload'])==expected and all(r['sequence']>freeze[0]['sequence'] for r in heldout), 'heldout_order_invalid')
        require(all(freeze[0]['payload'][cell_id]==row['incumbent_id'] for cell_id,row in cells_by_id.items()), 'global_incumbent_freeze_mismatch')
        require(all(digest(event['payload']['results'])==digest(cells_by_id[event['payload']['cell_id']]['heldout']) for event in heldout), 'heldout_results_summary_mismatch')
    if summary.get('scientific_claim_allowed'):
        require(protocol['mode']=='online' and len(heldout)==expected, 'scientific_claim_without_complete_heldout')
        require(summary['all_heldout_valid'] and all(summary['source_integrity'].values()), 'scientific_claim_without_integrity')
        require(all(c['status']=='completed' and c['heldout_valid'] for c in cells_by_id.values()), 'scientific_claim_with_incomplete_cells')
    require(digest(summarize_contrasts(protocol,summary['cells']))==digest(summary['rq_results']), 'rq_contrast_recalculation_mismatch')
    requests.extend(r['payload'] for r in study if r['kind']=='model_request')
    return {'status':'evidence_integrity_verified','study_status':summary['status'],
        'expected_cells':expected,'returned_cells':len(cells_by_id),'attempts_including_interrupted_cells':attempts,
        'valid_candidates':valid,'prospective_analyses':prospective,'admitted_counterexamples':admitted,
        'actions':dict(actions),'requests':len(requests),'failed_requests':sum(not r['ok'] for r in requests),
        'scientific_claim_allowed':summary.get('scientific_claim_allowed',False),
        'recalculated_from_journals':['quality_curves','analysis_prediction_metrics','paired_RQ_contrasts'],
        'boundary':'Integrity audit, not statistical significance or causal mechanism validation'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir',type=Path)
    args=parser.parse_args()
    print(json.dumps(audit(args.run_dir.resolve()),ensure_ascii=False,indent=2))
