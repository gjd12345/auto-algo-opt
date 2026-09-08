# auto-algo-opt (`agent-skill-loop-0908`)

This branch rebuilds the runtime around **one object**: an executable algorithm skill.

Give the loop `cvrp_construct`. It generates heuristic code, scores it in a subprocess, puts the real objective or error into the next prompt, and stops when the budget is exhausted. Beating a baseline is not a completion criterion.

Historical EoH / FME / RQ1b code is on `Refactor0830` (`c8cb66c`). Do not mix those numbers with this suite.

```powershell
py -3.11 -m pip install -e ".[dev]"
py -3.11 -c "import sys; assert sys.version_info[:2] == (3, 11); import agent_skill_loop"
py -3.11 -m pytest tests/kernel -q

py -3.11 -m agent_skill_loop prepare --problem cvrp_construct --output outputs/agent_skill/prepare
py -3.11 -m agent_skill_loop smoke --problem cvrp_construct --output outputs/agent_skill/smoke
```

Live model runs need `--model` and a **separate authorization**. An existing API key is not authorization.

Official EoH (`FeiLiu36/EoH` current `main`) is an optional extra. It keeps upstream operators (`e1`/`e2`/`m1`/`m2`) and scores the same frozen three-instance suite:

```powershell
py -3.11 -m pip install -e ".[dev,eoh]"
py -3.11 -m eoh_frozen run --model MODEL_NAME --output outputs/eoh_frozen/live --pop-size 4 --n-pop 5
```

```powershell
py -3.11 -m agent_skill_loop run --problem cvrp_construct --model MODEL_NAME --output outputs/agent_skill/live
py -3.11 -m agent_skill_loop evaluate-skill --skill outputs/agent_skill/live/exported_skill --suite outputs/agent_skill/live/dev_suite.json
```

Index of the frozen research inventory: [reports/research_convergence_20260908/03_route_catalog.md](reports/research_convergence_20260908/03_route_catalog.md).
