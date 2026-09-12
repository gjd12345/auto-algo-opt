"""Read-only production audit; only temporary Memory fixture files are created.

Run: py -3.11 reports/audit_20260912/probes.py
These probes report observed behavior, not assertions of successful acceptance.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import json
import tempfile
import threading
from types import SimpleNamespace
from unittest.mock import patch

from agent_skill_loop.memory import MemoryAPI, MemoryEntry
from agent_skill_loop.roles.plan import PlanPrompt, PlanRole
from agent_skill_loop.request_budget import RequestBudget
from agent_skill_loop.problems.base import get_problem
from agent_skill_loop.workflow import WorkflowRunner
from eoh_frozen.llm_bridge import OpenAIPathBridge
from eoh_frozen.repair import RepairingEOH, is_repairable
from eoh_frozen.export import export_run_evidence


def main():
    results = {}
    ref = 'cvrp_construct/insight_test@v0001'
    plan = dict(round_id=1, direction='test', operations=[dict(type='replace', target='scoring', mechanism='distance')],
                preserve='interface', feedback_basis=None, memory_basis=[ref], reference_skill_ref=None, hypothesis='unproven')
    reads = []
    prompt = PlanPrompt('cvrp_construct', 'suite', 1, None, None,
                        memory=({'reference': ref},), mode='select_memory')
    parsed = PlanRole(lambda *a, **k: json.dumps(plan)).run(
        prompt, read_memory=lambda r: reads.append(r) or {'reference': r, 'body': 'actual body'},
        expected_round_id=1, suite_hash='suite', available_memory_refs={ref})
    results['unread_memory_plan_accepted'] = {'reads': len(reads), 'accepted_refs': list(parsed.memory_basis)}

    response = json.dumps({'choices': [{'finish_reason': 'length', 'message': {
        'content': '', 'reasoning_content': 'def select_next_node(...):\n    pass'}}],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 16384}}).encode()
    bridge = OpenAIPathBridge('http://unused.local/v1/chat/completions', 'fixture', 'fixture',
                             budget=RequestBudget(2))
    with patch('eoh_frozen.llm_bridge.http_post_with_deadline', return_value=(200, response)):
        forwarded = bridge._forward('fixture generation')
    results['truncated_reasoning_forwarded'] = {'forwarded': forwarded, 'terminal': bridge.terminal}

    results['repair_policy'] = {
        'forbidden_rebinding': is_repairable({'error_code': 'forbidden_rebinding', 'error_detail': 'np'}),
        'forbidden_read_text': is_repairable({'error_code': 'forbidden_attribute', 'error_detail': 'read_text'}),
        'unknown_exception': is_repairable({'error_code': 'candidate_exception', 'error_detail': 'UnknownError'})}

    engine = object.__new__(RepairingEOH)
    engine._repair_lock = threading.Lock()
    engine.max_repairs_per_candidate = 1
    engine.max_repair_requests_total = 1
    for field in ('repair_triggered', 'repair_attempted', 'repair_succeeded', 'repair_failed', 'repair_skipped'):
        setattr(engine, field, 0)
    spec = get_problem('cvrp_construct')
    engine.problem = SimpleNamespace(spec=spec, task_description=spec.task_description,
        template_program=spec.template_program, suite={'content_hash': 'suite'}, timeout=20,
        set_evaluation_context=lambda c: None)
    engine.repair_request = lambda *a, **k: json.dumps({
        'algorithm': 'fixed', 'code': spec.baseline_code, 'repair_summary': 'fixed'})
    engine._eval_executor = SimpleNamespace(submit=lambda *a, **k: SimpleNamespace(result=lambda: 1.0))
    engine._diagnose = lambda code: None
    events = []
    engine._append_repair_event = events.append
    off = engine._repair_one(offspring={'code': 'def broken(): pass', 'objective': None},
        operator='i1', candidate_id='candidate_1', diagnostic={'error_code': 'missing_entrypoint'})
    results['missing_repair_evidence_accepted'] = {
        'objective': off['objective'], 'state': events[-1]['state'], 'evaluation': events[-1]['evaluation']}

    with tempfile.TemporaryDirectory(prefix='memory-audit-') as tmp:
        memory = MemoryAPI(Path(tmp))
        entry = MemoryEntry('test', 'test experience', 'insight', 'cvrp_construct', 'select_next_node',
                            '**Why:** observed.\n\n**How to apply:** bounded conditions.')
        written = memory.write(entry)
        loaded = memory.read_version(written['reference'], max_chars=1)
        results['memory_read_limit'] = {'requested_chars': 1, 'returned_chars': len(loaded['body']),
                                       'truncated_flag': loaded['truncated']}
        index = memory.read_index(project='cvrp_construct', scene='select_next_node', limit=1)
        results['memory_index_returns_body'] = 'body' in index['memories'][0]

    # Fault-injection boundary: complete baseline evidence followed by an interrupted
    # repair whose final event was not durably written. No real export files are made.
    suite = spec.build_suite(20260908, count=1, size=6)
    from agent_skill_loop.skill_store import sha256_text
    baseline = {'origin': 'baseline', 'entrypoint': spec.entrypoint, 'code': spec.baseline_code,
                'code_sha256': sha256_text(spec.baseline_code), 'evaluation_line': 1,
                'evaluation': {'valid': True, 'objective': 10.0, 'instance_objectives': [10.0]}}
    repair = {'origin': 'generated_repair', 'entrypoint': spec.entrypoint, 'code_sha256': 'b',
              'candidate_id': 'candidate_1', 'evaluation_id': 'repair-eval', 'evaluation': {'valid': False}}
    with patch('eoh_frozen.export.read_evidence', return_value=[baseline, repair]), \
         patch('eoh_frozen.export._read_repair_records', return_value=[]), \
         patch('eoh_frozen.export.checkpoint_individuals', return_value=[]), \
         patch('eoh_frozen.export.save_skill'), \
         patch('eoh_frozen.export.publish_export_ref') as publish, \
         patch.object(Path, 'exists', return_value=False):
        try:
            export_run_evidence(Path('audit-not-written'), suite)
            outcome = 'completed'
        except ValueError as exc:
            outcome = str(exc)
        results['interrupted_repair_export'] = {'outcome': outcome, 'baseline_ref_published': publish.called}

    # Check the real workflow wiring, rather than calling the gate with a richer
    # fixture than its production caller supplies.
    import inspect
    source = inspect.getsource(WorkflowRunner._run_round)
    results['solution_gate_wiring'] = {
        'passes_eoh_summary_not_enriched_facts': '_write_memory_action(round_root, evaluation, execute_summary)' in source}
    from agent_skill_loop.evaluator import evaluator_source_hash
    runner = object.__new__(WorkflowRunner)
    runner.spec = spec
    runner.problem = spec.problem_id
    runner.suite = suite
    runner.solution_min_relative_improvement = 0.05
    candidate = SimpleNamespace(problem=spec.problem_id, entrypoint=spec.entrypoint,
        suite_hash=suite['content_hash'], evaluator_hash=evaluator_source_hash(),
        valid=True, mean_objective=9.0, code_sha256='candidate-hash')
    summary = {'generated_valid_candidates': 1, 'best_generated_path': 'skills/candidate_1',
               'baseline': {'objective': 10.0}}
    facts = {**summary, 'evaluations': [{'evaluation_line': 2, 'code_sha256': 'candidate-hash',
        'problem': spec.problem_id, 'entrypoint': spec.entrypoint, 'source_request_index': 2,
        'evaluation': {'valid': True, 'suite_hash': suite['content_hash'], 'objective': 9.0}}]}
    action = SimpleNamespace(evidence_ref='skills/candidate_1', based_on=None)
    with patch('agent_skill_loop.workflow.load_skill', return_value=candidate), \
         patch.object(Path, 'is_file', return_value=True), \
         patch.object(Path, 'read_text', return_value=json.dumps({
             'evaluation_line': 2, 'local_objective': 9.0, 'source_request_index': 2})):
        results['solution_gate_wiring']['with_enriched_facts'] = runner._solution_eligible(Path('unused'), facts, action)
        results['solution_gate_wiring']['with_actual_summary_shape'] = runner._solution_eligible(Path('unused'), summary, action)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
