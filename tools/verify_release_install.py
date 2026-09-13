"""Build/install the wheel outside the checkout and verify real Skill identity.

Uses a temporary venv with system dependencies (numpy/build tooling), but
asserts that both Runtime and Skill come from the newly installed wheel.
No provider request or solver execution is made.
"""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import venv


def main():
    repo = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)

    def run(args, cwd):
        result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=180)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        return result.stdout

    expected = run([sys.executable, "-c", "from agent_skill_loop.session_runtime import _skill_content_hash; print(_skill_content_hash())"], repo).strip()
    with tempfile.TemporaryDirectory(prefix="algorithm-release-") as temporary:
        work = Path(temporary)
        run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(work), str(repo)], work)
        wheel, = work.glob("agent_skill_loop-*.whl")
        venv.EnvBuilder(with_pip=True, system_site_packages=True).create(work / "venv")
        python = work / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run([str(python), "-m", "pip", "install", "--no-deps", "--force-reinstall", str(wheel)], work)
        script = '''
import json, sys
from pathlib import Path
import agent_skill_loop, algorithm_optimization_skill
from agent_skill_loop import session_runtime as db
prefix = Path(sys.prefix).resolve()
assert Path(agent_skill_loop.__file__).resolve().is_relative_to(prefix)
skill = Path(algorithm_optimization_skill.__file__).resolve().parent
assert skill.is_relative_to(prefix)
assert (skill / 'references/benchmark.md').is_file()
assert (skill / 'references/examples/two-round-run.md').is_file()
assert db._skill_content_hash() == sys.argv[1]
db.initialize_session(output=Path('run'), operation_id='init', eoh_model='offline-check', size=6, count=1)
state = db.read_state(run=Path('run'))
assert state['integrity']['skill_identity'] == 'ok'
assert state['integrity']['runtime_identity'] == 'ok'
assert state['feedback_basis'] is None
assert not any(x.startswith('eoh.') for x in sys.modules)
print(json.dumps({'wheel_install': 'passed', 'skill_sha256': db._skill_content_hash(), 'session_init_state': 'passed', 'provider_requests': 0}))
'''
        print(run([str(python), "-c", script, expected], work).strip())


if __name__ == "__main__":
    main()
