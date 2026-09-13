"""Regression contracts for the thirteen 2026-09-12 audit findings (no paid API)."""
import json
from dataclasses import replace

import pytest

from agent_skill_loop.evaluator import evaluator_source_hash
from agent_skill_loop.memory import MemoryAPI, MemoryEntry
from agent_skill_loop.problems.base import get_problem
from agent_skill_loop.request_budget import RequestBudget, BudgetExhausted
from agent_skill_loop.skill_store import load_skill, sha256_text
from eoh_frozen.export import export_run_evidence, _repair_record_for_row
from eoh_frozen.llm_bridge import OpenAIPathBridge


def evidence(spec, suite, code, objective, origin, **identity):
    return dict(code=code, code_sha256=sha256_text(code), problem=spec.problem_id,
        entrypoint=spec.entrypoint, suite_hash=suite['content_hash'], evaluator_hash=evaluator_source_hash(),
        origin=origin, evaluation_id=origin, evaluation=dict(valid=True, objective=objective,
        instance_objectives=[objective] * len(suite['instances']), suite_hash=suite['content_hash']), **identity)


def write_rows(root, rows):
    path = root / 'results/evaluations.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(json.dumps(row) for row in rows) + '\n', encoding='utf-8')


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
