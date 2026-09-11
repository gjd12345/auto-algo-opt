# agent_skill_loop

Given a registered problem (`cvrp_construct`, `tsp_construct`, `tsp_2opt`), generate algorithm code, evaluate it in a subprocess, feed the real objective or error into the next prompt, and stop when the budget is exhausted.

This package does **not** import `eoh_rag.fme`. It does not require the incumbent to beat a baseline.

```powershell
py -3.11 -m agent_skill_loop prepare --problem cvrp_construct --output outputs/agent_skill/prepare
py -3.11 -m agent_skill_loop smoke --problem cvrp_construct --output outputs/agent_skill/smoke
py -3.11 -m pytest tests/kernel -q
```

Import one named historical candidate (git snapshot or local file). The source
ref/commit/path/hash/license is recorded, the code is re-evaluated on the
current suite with the current evaluator, and it is stored as a reusable skill
only when valid. Historical scores never migrate, and imports are not counted
as generated candidates.

```powershell
py -3.11 -m agent_skill_loop import-skill --problem cvrp_construct --output outputs/agent_skill/import_x --git-repo . --git-ref main --git-path evidence/final_batch_20260630/best_codes/cvrp_construct_best.py --license "see repo LICENSE"
py -3.11 -m agent_skill_loop evaluate-skill --skill outputs/agent_skill/import_x/exported_skill --suite outputs/agent_skill/import_x/dev_suite.json
```

Live model runs need an explicit `--model` and a separate authorization. Existing API keys are not authorization.
