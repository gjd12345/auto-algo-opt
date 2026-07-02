# How to Reproduce

## Prerequisites

- Python 3.10+ with numpy
- Official EoH at `/private/tmp/EoH-main` (or set EOH_OFFICIAL_ROOT)
- EoH venv at `/private/tmp/eoh_official_venv` (or set EOH_OFFICIAL_PYTHON)
- API key in `~/.config/agent_go/opencode.env`

## Replay Best Code

```bash
# BP Online replay (exact result)
/private/tmp/eoh_official_venv/bin/python -c "
import sys; sys.path.insert(0, '/private/tmp/EoH-main/examples/bp_online')
from prob import BPONLINE
import numpy as np

def score(item, bins):
    residual = bins - item
    utilization = np.exp(item / (residual + item + 1e-9))
    penalty = np.where((residual > 0) & (residual < 2*item), (residual - item)**2 / (item + 1e-9), 0)
    return utilization - penalty

print(BPONLINE(capacity=100).evaluate_program('', score))
# Expected: 0.006741
"
```

## Rerun Full Batch

```bash
export $(grep -v '^#' ~/.config/agent_go/opencode.env | xargs)
bash scripts/launch_island.sh
# Wait ~7h for 600+ runs
```

## Verify Consistency

```bash
python3 -c "
import json
status = json.loads(open('evidence/final_batch_20260630/batch_status.json').read())
print(f'Total: {status[\"total_runs\"]} runs')
for p, info in status['problems'].items():
    print(f'  {p}: best={info[\"best\"]}, improvement={info[\"improvement_best\"]*100:.1f}%')
"
```
