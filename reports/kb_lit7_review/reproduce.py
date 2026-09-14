"""Offline review probes; never mutate workspace content or releases."""
import copy
import json
from pathlib import Path
from unittest.mock import patch
from knowledge_tools import core
from knowledge_tools.dashboard import _entry_payload, _family_meta, _card_html

release = Path('knowledge_store/releases/20260914-main-d6433549-kb-lit7')
workspace = Path('knowledge_workspace')
index = core.read_json(release / 'index.json')
taxonomy = core.read_json(release / 'taxonomy.json')
original = core.read_json
target = next(workspace.joinpath('entries').glob('method-lit-*.json'))

def forged(path):
    data = original(path)
    if Path(path).resolve() == target.resolve():
        data['status'] = 'validated'
        data['evidence_refs'] = ['evaluation:missing-report-without-suite-metric-budget']
        data['relations'] = {'problems': ['problem-does-not-exist']}
    return data

with patch.object(core, 'read_json', side_effect=forged):
    result = core.validate_workspace(workspace)
    print('forged_evidence_and_relation_accepted', result['ok'])
    assert result['ok'], result['errors']

meta = _family_meta(index, taxonomy)
query = 'TSP 2-opt'
from html.parser import HTMLParser
class Cards(HTMLParser):
    def __init__(self):
        super().__init__()
        self.matches = 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'data-search' in attrs and query.lower() in attrs['data-search']:
            self.matches += 1
parser = Cards()
for entry in index['entries']:
    parser.feed(_card_html(_entry_payload(entry, meta)))
print('frontend_literal_search_hits', parser.matches)
print('backend_search_hits', core.search_release(release, query, 3)['total'])

changed = copy.deepcopy(index['entries'])
changed[0]['status'] = 'review-probe'
changed[0]['source_refs'] = ['src-does-not-exist']
print('metadata_only_diff', core._version_diff(release, changed)['changed_count'])

# Keep byte differences caused only by Python set iteration distinct from
# semantic frontend drift.
import re
from knowledge_tools.dashboard import dashboard_html
load = lambda name: original(release / name)
pending = [e for e in index['entries'] if e.get('status') in {'pending', 'unread'} or e.get('category') == 'pending']
generated = dashboard_html(release.name, index, taxonomy, load('sources.json'), pending, load('version_diff.json'), load('inventory.json'))
published = (release / 'dashboard.html').read_text(encoding='utf-8')
normalise = lambda text: re.sub(r'const FAMILY_LABELS = .*?;', 'const FAMILY_LABELS = {};', text)
print('dashboard_matches_except_family_key_order', normalise(generated) == normalise(published))
