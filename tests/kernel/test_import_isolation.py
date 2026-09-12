import subprocess
import sys


def test_production_imports_neither_fixture_search_nor_optional_engine():
    script = '''
import importlib.util, sys
import agent_skill_loop.__main__, agent_skill_loop.evaluator, eoh_frozen.export
import agent_skill_loop.client, agent_skill_loop.roles
from agent_skill_loop.problems.base import ProblemSpec
assert not any(n in ProblemSpec.__dataclass_fields__ for n in ('repair_hint', 'stagnation_hint', 'interface_boundary'))
assert 'eoh' not in sys.modules
assert not any(n.startswith('tests.fixtures') or n.startswith('eoh_rag') for n in sys.modules)
assert importlib.util.find_spec('agent_skill_loop.roles.client') is None
for module in ('agent_skill_loop.loop', 'agent_skill_loop.generator', 'agent_skill_loop.policy'):
    assert importlib.util.find_spec(module) is None, module
'''
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
