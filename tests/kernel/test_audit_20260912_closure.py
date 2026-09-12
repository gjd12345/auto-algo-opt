"""Regression contracts for the thirteen 2026-09-12 audit findings (no paid API)."""
import json
import threading
from dataclasses import replace
from types import SimpleNamespace

import pytest

from agent_skill_loop.contracts_3plus1 import PlanDocument, compile_round_context
from agent_skill_loop.evaluator import evaluator_source_hash
from agent_skill_loop.memory import MemoryAPI, MemoryEntry
from agent_skill_loop.problems.base import get_problem
from agent_skill_loop.request_budget import RequestBudget, BudgetExhausted
from agent_skill_loop.roles.plan import PlanPrompt, PlanRole
from agent_skill_loop.skill_store import load_skill, sha256_text
from agent_skill_loop.workflow import WorkflowRunner
from eoh_frozen.export import export_run_evidence, _repair_record_for_row
from eoh_frozen.llm_bridge import OpenAIPathBridge
from eoh_frozen.problem import FrozenProblem
from eoh_frozen.repair import RepairingEOH, is_repairable


def plan_payload(prompt, **_):
    data = json.loads(prompt)
    return json.dumps(dict(round_id=data['round_id'], direction='change scoring',
        operations=[dict(type='replace', target='scoring', mechanism='distance')],
        preserve='interface', feedback_basis=data.get('feedback_reference'),
        memory_basis=[], reference_skill_ref=None, hypothesis='unproven'))


def evidence(spec, suite, code, objective, origin, **identity):
    return dict(code=code, code_sha256=sha256_text(code), problem=spec.problem_id,
        entrypoint=spec.entrypoint, suite_hash=suite['content_hash'], evaluator_hash=evaluator_source_hash(),
        origin=origin, evaluation_id=origin, evaluation=dict(valid=True, objective=objective,
        instance_objectives=[objective] * len(suite['instances']), suite_hash=suite['content_hash']), **identity)


def write_rows(root, rows):
    path = root / 'results/evaluations.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(json.dumps(row) for row in rows) + '\n', encoding='utf-8')


def test_missing_repair_evidence_never_accepts_scalar_fitness():
    engine = object.__new__(RepairingEOH)
    engine._repair_lock = threading.Lock()
    engine.max_repairs_per_candidate = engine.max_repair_requests_total = 1
    for name in ('repair_triggered', 'repair_attempted', 'repair_succeeded', 'repair_failed', 'repair_skipped'):
        setattr(engine, name, 0)
    spec = get_problem('cvrp_construct')
    engine.problem = SimpleNamespace(spec=spec, task_description=spec.task_description,
        template_program=spec.template_program, suite={'content_hash': 'suite'}, timeout=20,
        set_evaluation_context=lambda _: None, evaluation_for_identity=lambda *_: None)
    engine.repair_request = lambda *a, **k: json.dumps(dict(algorithm='fixed', code=spec.baseline_code, repair_summary='fixed'))
    engine._eval_executor = SimpleNamespace(submit=lambda *a: SimpleNamespace(result=lambda: 1.0))
    events = []
    engine._append_repair_event = events.append
    offspring = engine._repair_one(offspring=dict(code='def broken(): pass', objective=None),
        operator='i1', candidate_id='candidate_1', diagnostic={'error_code': 'missing_entrypoint'})
    assert offspring['objective'] is None and events[-1]['state'] == 'failed'
    assert engine.repair_succeeded == 0


def test_partial_repair_quarantined_baseline_preserved_and_exact_identity(tmp_path):
    spec = get_problem('cvrp_construct')
    suite = spec.build_suite(1, count=1, size=6)
    baseline = evidence(spec, suite, spec.baseline_code, 10., 'baseline')
    repaired = evidence(spec, suite, spec.baseline_code + '\n#repair', 9., 'generated_repair',
                        candidate_id='candidate_1', revision='repair_1', original_code_sha256='original')
    write_rows(tmp_path, [baseline, repaired])
    result = export_run_evidence(tmp_path, suite)
    assert result['export_status'] == 'published'
    assert len(result['quarantined_evaluations']) == 1
    assert load_skill(tmp_path / 'exported_skill').origin == 'baseline'
    assert export_run_evidence(tmp_path, suite)['export_status'] == 'published'
    # Equal code alone cannot bind a terminal event from another evaluation.
    assert _repair_record_for_row([dict(state='succeeded', candidate_id='candidate_1',
        evaluated_code_sha256=repaired['code_sha256'], repair_evaluation_id='other')], repaired) is None
    problem = FrozenProblem(suite, spec=spec, evaluation_log=tmp_path / 'results/evaluations.jsonl')
    assert problem.evaluation_for_identity(repaired['code'], dict(candidate_id='candidate_1',
        revision='repair_1', evaluation_id='other')) is None


def test_workflow_solution_publication_uses_enriched_facts_and_frozen_gate(tmp_path):
    observed = []
    def evaluate(prompt, **_):
        facts = json.loads(prompt)['trusted_facts']
        observed.append(facts)
        return json.dumps(dict(plan_alignment='unknown', observations=[], causal_claim='unproven',
            memory_action=dict(kind='solution', name='better', description='fixture solution',
                project='cvrp_construct', scene='select_next_node',
                body='**Reusable Experience:** re-evaluate before reuse.', evidence_ref=facts['best_generated_path'])))
    def run(name, threshold):
        runner = WorkflowRunner(tmp_path / name, model='fixture', count=1, size=6,
            max_rounds=1, plan_request=plan_payload, evaluate_request=evaluate,
            memory=MemoryAPI(tmp_path / (name + '-memory')), solution_min_relative_improvement=threshold)
        def execute(round_root, **_):
            root = round_root / 'eoh_run'
            rows = [evidence(runner.spec, runner.suite, runner.spec.baseline_code, 10., 'baseline'),
                    evidence(runner.spec, runner.suite, runner.spec.baseline_code + '\n#variant', 9., 'generated')]
            write_rows(root, rows)
            return dict(export_run_evidence(root, runner.suite), status='completed', http_requests=0,
                        baseline={'objective': 10.}, suite_hash=runner.suite['content_hash'])
        runner._execute = execute
        assert runner.run()['status'] == 'completed'
        return runner.root / 'rounds/round_0001'
    allowed = run('configured', .05)
    denied = run('unconfigured', None)
    assert json.loads((allowed / 'memory_result.json').read_text())['written']
    assert (denied / 'memory_rejected.json').exists()
    assert observed[0]['evaluations'][1]['evaluation_id'] == 'generated'
    assert '#variant' in observed[0]['code_evidence'][-1]['code']
    assert get_problem('cvrp_construct').solution_improvement(0, -1) is None


def test_plan_cannot_bypass_read_and_context_is_deduplicated_bounded():
    ref = 'cvrp_construct/insight_test@v0001'
    prompt = PlanPrompt('cvrp_construct', 'suite', 1, None, None,
        memory=({'reference': ref},), mode='select_memory')
    data = json.loads(plan_payload(prompt.render()))
    data['memory_basis'] = [ref]
    reads = []
    with pytest.raises(ValueError):
        PlanRole(lambda *a, **k: json.dumps(data)).run(prompt,
            read_memory=lambda r: reads.append(r), expected_round_id=1,
            suite_hash='suite', available_memory_refs={ref})
    assert not reads
    plan = PlanDocument.from_dict(data, expected_round_id=1, suite_hash='suite', available_memory_refs={ref})
    item = dict(reference=ref, body='x' * 8000, body_sha256='bodyhash', truncated=False)
    context = compile_round_context(plan, memory_summaries=[item, item])
    assert len(json.loads(context.split('\n', 1)[1])['memory']) == 1
    small = json.loads(compile_round_context(plan, memory_summaries=[item], max_chars=1000).split('\n', 1)[1])
    assert small['memory'] == [] and small['omitted_memory_refs'] == [ref]
    escaped = compile_round_context(replace(plan, preserve='\x01' * 4096))
    assert len(escaped) <= 12000 and json.loads(escaped.split('\n', 1)[1])['advisory_omitted']


def test_memory_paging_cas_history_merge_and_index_failure(tmp_path, monkeypatch):
    api = MemoryAPI(tmp_path)
    entry = MemoryEntry('one', 'description', 'insight', 'cvrp_construct', 'select_next_node',
                        '**Why:** reason\n\n**How to apply:** same suite')
    entry = replace(entry, body=entry.body + '汉' * (8000 - len(entry.body)))
    first = api.write(entry)
    page = api.read_version(first['reference'], max_chars=1)
    assert len(page['body']) == 1 and page['next_offset'] == 1 and page['truncated']
    assert 'body' not in api.read_index(project=entry.project, scene=entry.scene)['memories'][0]
    with pytest.raises(ValueError):
        api.write(replace(entry, name='long', body=entry.body + 'x'))
    with api._writer(), pytest.raises(ValueError, match='memory_writer_busy'):
        api.write(replace(entry, name='locked'))
    second = api.write(replace(entry, body='**Why:** new\n\n**How to apply:** bounded'), based_on=first['reference'])
    assert len(api.read_version(first['reference'])['body']) == 8000
    with pytest.raises(ValueError, match='not_latest'):
        api.write(entry, based_on=first['reference'])
    monkeypatch.setattr(api, 'reindex', lambda: (_ for _ in ()).throw(OSError('disk')))
    merged = api.write(replace(entry, name='merged'), related_refs=(second['reference'],))
    assert merged['written'] and not merged['index_updated']
    from pathlib import Path
    assert json.loads(Path(merged['path']).with_suffix('.json').read_text())['related_refs'] == [second['reference']]


def test_response_policy_rejects_drafts_and_reserves_every_retry(tmp_path, monkeypatch):
    budget = RequestBudget(2)
    bridge = OpenAIPathBridge('http://fixture', 'fixture', 'fixture', budget=budget,
                             request_log=tmp_path / 'requests.jsonl')
    for finish, content in [('length', 'def incomplete('), ('stop', '')]:
        raw = dict(choices=[dict(finish_reason=finish, message=dict(content=content, reasoning_content='draft code'))],
                   usage={'completion_tokens': 9})
        monkeypatch.setattr('eoh_frozen.llm_bridge.http_post_with_deadline', lambda *a: (200, json.dumps(raw).encode()))
        with pytest.raises(ValueError):
            bridge._forward('generate')
    assert budget.used == 2
    with pytest.raises(BudgetExhausted):
        bridge._forward('third')
    records = [json.loads(p.read_text()) for p in (tmp_path / 'exchanges').glob('request_*.json')]
    assert all(row['selected_content_field'] is None and row['raw_response'] for row in records)


def test_repair_policy_is_closed():
    for code, detail in [('forbidden_rebinding', 'np'), ('forbidden_attribute', 'read_text'),
                         ('candidate_exception', 'UnknownError'), ('timeout', ''), ('unknown', '')]:
        assert not is_repairable({'error_code': code, 'error_detail': detail})
    assert is_repairable({'error_code': 'forbidden_attribute', 'error_detail': 'ix_'})
    assert is_repairable({'error_code': 'candidate_exception', 'error_detail': 'NameError:line_3'})


def test_evaluate_cannot_claim_alignment_without_code():
    from agent_skill_loop.roles.evaluate import EvaluateRole, EvaluatePrompt
    response = json.dumps(dict(plan_alignment='aligned', observations=[], causal_claim='proven', memory_action={'kind': 'disabled'}))
    result = EvaluateRole(lambda *a, **k: response).run(EvaluatePrompt('cvrp_construct', 'suite', {}, {}, False))
    assert result.plan_alignment == 'unknown' and result.causal_claim == 'unproven'
