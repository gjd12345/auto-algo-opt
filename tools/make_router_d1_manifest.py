"""Derive a D1 manifest from the registered pilot while changing provider identity."""
from __future__ import annotations
import json
from pathlib import Path
from eoh_frozen.generation_contract import generation_contract

def main() -> None:
    env = {}
    for line in Path('.env').read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    payload = json.loads(Path('outputs/obp_abcd_real_20260915_01/pilot_manifests.json').read_text(encoding='utf-8'))
    manifest = dict(payload['groups']['D']['manifest'])
    manifest['model'] = 'qwen/deepseek-v4.1-flash'
    manifest['endpoint_identity'] = env['MODEL_ROUTER_ENDPOINT']
    extra = dict(manifest['extra'])
    extra['api_key_env'] = 'MODEL_ROUTER_API_KEY'
    extra['generation_contract'] = generation_contract(manifest['model'], manifest['endpoint_identity'], 'provider-default', 180)
    extra['prior_attempt'] = {
        'run_id': 'run_ec670f23b3e7447aa28f692369cf82a3',
        'reason': 'provider_auth_invalid', 'requests': 1,
        'new_run_reason': 'use repository-configured model-router credential and requested qwen/deepseek-v4.1-flash',
    }
    manifest['extra'] = extra
    Path('reports/d1_pilot_20260915/router_pilot_manifest.json').write_text(
        json.dumps({'groups': {'D': {'manifest': manifest}}}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

if __name__ == '__main__':
    main()
