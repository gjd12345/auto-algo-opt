"""Read-only repository inventory; writes only its audit JSON beside this file."""
from pathlib import Path
import ast
from collections import Counter, defaultdict
import hashlib
import json
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8').strip()

tracked = git('ls-files', '-z').split('\0')
stats = defaultdict(lambda: {'files': 0, 'bytes': 0})
missing = []
for name in tracked:
    path = ROOT / name
    if not path.exists():
        missing.append(name)
        continue
    bucket = name.split('/')[0] if '/' in name else '(root files)'
    stats[bucket]['files'] += 1
    stats[bucket]['bytes'] += path.lstat().st_size

local = {}
for folder in ['outputs', 'build', '.pytest_cache', 'agent_skill_loop.egg-info', 'eoh_rag.egg-info', 'configs']:
    files = []
    for base, dirs, names in os.walk(ROOT / folder, followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(base) / d).is_symlink()]
        files.extend(Path(base) / n for n in names)
    local[folder] = {'files': len(files), 'bytes': sum(p.stat().st_size for p in files)}

code = [p for folder in ['agent_skill_loop', 'eoh_frozen', 'knowledge_tools', 'tools'] for p in (ROOT / folder).rglob('*.py')]
syntax = []
sizes = []
duplicates = defaultdict(list)
for p in code:
    raw = p.read_bytes()
    sizes.append({'path': p.relative_to(ROOT).as_posix(), 'lines': len(raw.splitlines())})
    try:
        ast.parse(raw, filename=str(p))
    except SyntaxError as exc:
        syntax.append({'path': str(p), 'error': str(exc)})
    if raw.strip():
        duplicates[hashlib.sha256(raw).hexdigest()].append(p.relative_to(ROOT).as_posix())

docs = [ROOT / 'README.md', ROOT / 'agent_skill_loop/README.md']
docs += list((ROOT / 'docs').glob('*.md'))
docs += list((ROOT / 'skills/algorithm-optimization').rglob('*.md'))
docs += list((ROOT / 'reports').glob('*.md'))
broken = []
absolute = []
for p in docs:
    for number, line in enumerate(p.read_text(encoding='utf-8').splitlines(), 1):
        for target in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)', line):
            target = target.strip('<>')
            if re.match(r'^[A-Za-z]:[/\\]', target):
                absolute.append({'path': p.relative_to(ROOT).as_posix(), 'line': number, 'target': target})
                continue
            if target.startswith(('#', 'http:', 'https:', 'mailto:')):
                continue
            target = target.split('#')[0]
            if target and not (p.parent / target).exists():
                broken.append({'path': p.relative_to(ROOT).as_posix(), 'line': number, 'target': target})

transcripts = {}
for name in ['Knowledge_base_construct.md', 'session-ses_f616.md']:
    p = ROOT / name
    transcripts[name] = {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                         'lf_normalized_sha256': hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()}

bundles = []
bundle_roots = [ROOT / 'reports/evidence/real_wiring_deepseek_20260915']
bundle_roots += [ROOT / 'outputs/obp_abcd_real_20260915_01/evidence' / g for g in 'ABCD']
for folder in bundle_roots:
    hashes = json.loads((folder / 'SHA256SUMS.json').read_text(encoding='utf-8'))
    failures = []
    for name, expected in hashes.items():
        p = folder / name
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            failures.append(name)
    bundles.append({'path': folder.relative_to(ROOT).as_posix(), 'checked_files': len(hashes), 'failures': failures})

build_drift = []
for p in (ROOT / 'build/lib').rglob('*.py'):
    rel = p.relative_to(ROOT / 'build/lib')
    source = ROOT / rel
    if source.exists() and p.read_bytes() != source.read_bytes():
        build_drift.append(rel.as_posix())

result = {'head': git('rev-parse', 'HEAD'), 'branch': git('branch', '--show-current'),
          'tracked_count': len(tracked), 'tracked_by_root': dict(sorted(stats.items())),
          'missing_tracked_paths': missing, 'local_generated': local,
          'python_files_scanned': len(code), 'syntax_errors': syntax,
          'largest_python_modules': sorted(sizes, key=lambda x: -x['lines'])[:12],
          'identical_nonempty_python_files': [v for v in duplicates.values() if len(v) > 1],
          'document_files_link_scanned': len(docs), 'missing_local_link_targets': broken,
          'machine_absolute_links': absolute, 'transcripts': transcripts,
          'evidence_bundle_integrity': bundles, 'build_python_different_from_source': build_drift,
          'test_files': dict(Counter(p.parent.name for p in (ROOT / 'tests').rglob('test_*.py')))}
out = Path(__file__).with_name('inventory.json')
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
