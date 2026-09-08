# agent_skill_loop

Given `cvrp_construct`, generate heuristic code, evaluate it in a subprocess, feed the real objective or error into the next prompt, and stop when the budget is exhausted.

This package does **not** import `eoh_rag.fme`. It does not require the incumbent to beat a baseline.

```powershell
py -3.11 -m agent_skill_loop prepare --problem cvrp_construct --output outputs/agent_skill/prepare
py -3.11 -m agent_skill_loop smoke --problem cvrp_construct --output outputs/agent_skill/smoke
py -3.11 -m pytest tests/kernel -q
```

Live model runs need an explicit `--model` and a separate authorization. Existing API keys are not authorization.
