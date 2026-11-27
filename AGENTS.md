# Repository Agent & Dual-Model Workflow Rules (`auto-algo-opt`)

Always apply these rules automatically in this repository without waiting for the user to ask on each turn.

## 1. Bidirectional Dual-Model Workflow (Codex CLI + Antigravity Mutual Verification)

The user maintains high OpenAI Codex CLI quota (`codex-bridge_codex` MCP tools). Coordinate work so **neither model grades its own complex implementation**:

1. **Heavy Engineering -> Delegate to Codex, Audit in Antigravity:**
   - For multi-file feature delivery (e.g., M3.1 TSP/OBP adapters, M3.2 scaling runners, M4 Shapley/statistical tooling), standalone scripts, bug-fix batches, or new test suites, proactively route execution to Codex via `codex_plan` -> `codex_run(sandbox="workspace-write")` or disjoint non-overlapping `codex-worker` slices.
   - Ask the user before mutating files on genuinely ambiguous or destructive architectural changes; otherwise dispatch cleanly with a crisp Engineering Brief (Goal, Non-Goals, Target Paths, Invariants, Verification Commands).
   - After Codex completes, **Antigravity MUST strictly audit**: inspect `changed_files` & `pre_existing_dirty_files`, read touched files with `read_file` for `0`/`None` falsy traps and edge cases, and run the actual `pytest` / validators directly before accepting.

2. **Critical Antigravity Changes & Pre-Run Gates -> Automatic Codex Read-Only Red-Team Audit:**
   - Whenever Antigravity edits state machines, `PersistentRequestBudget` / `SessionRequestBudget`, custody/blind isolation guards, `InterfaceValidator` gates, statistical tests, or experiment runners — and **always before** launching expensive multi-seed/large-budget LLM experiments, building immutable releases, or pushing milestone commits — automatically run Codex in strict read-only audit mode (`codex_review` or `codex_run(sandbox="read-only")` or parallel read-only `codex-worker` slices).
   - Pass explicit **Immutable Redlines** and **Domain Invariants** in the Audit Brief, and demand `P0/P1/P2` severity with `file:line` + counterexamples. Verify findings against source to filter false positives, then fix real `P0/P1` issues centrally.

3. **Mathematical Derivation, Theorem Discovery & Experimental Theoretical Abstraction -> Codex Leads (`reasoning_effort="high"`), Antigravity Verifies & Translates:**
   - Do **not** confine Codex solely to code building or bug auditing. Proactively invoke Codex (`codex_run(sandbox="read-only", reasoning_effort="high")`) as Chief Mathematical Theorist to:
     - **Theory-First Experiment Design:** Derive formal definitions, lemmas, theorems, tight upper/lower bounds, and explicit counterexamples *before* coding new algorithmic mechanisms (e.g., radial integral bounds, complexity-escape latency models, adaptive stopping risk bounds, fleet-aware constraints).
     - **Post-Experiment Abstraction & Unification:** Synthesize raw empirical tables, AST structures, and failure modes into high-level mathematical abstractions, unified theoretical frameworks, and proof boundary stress-tests (constructing edge-case counterexamples such as rounding/triangle-inequality violations).
   - **Antigravity Verification & Translation:** Independently run numerical/programmatic verification scripts against raw data for every formula or theorem Codex proposes, then translate validated theory into clear, jargon-free academic prose and publication-grade figures (for Fudan Academic Master's thesis, IJCAI/NeurIPS papers, and defense slides).

4. **Lightweight Tasks -> Antigravity Direct:**
   - Q&A, file reading, progress status checks, git inspection, and prose/Obsidian documentation edits stay in Antigravity directly without Codex overhead.

5. **Codex Quota Exhaustion Fallback (Non-Blocking Continuity):**
   - If Codex quota/rate limit is exhausted (or the user indicates Codex is cooling down), **immediately pause all `codex-bridge_codex` calls** instead of retrying or blocking the workflow.
   - During Codex recovery, Antigravity (Gemini) should proactively continue all tasks that do not require Codex — including local environment/toolchain setup (e.g., LaTeX, `python-pptx`), paper/thesis/PPT drafting, figure generation, architecture/experiment planning, and read-only data/code inspection.
   - Defer Codex-gated high-risk milestones (e.g., launching expensive multi-seed paid LLM batches or publishing final immutable KB releases that require a pre-run Codex red-team audit) until Codex quota recovers, unless the user explicitly waives the gate; clearly notify the user what was completed independently and what is queued for Codex upon recovery.

## 2. `tmux`-Style Multi-Task Concurrency for Experiments & Agents

Never execute independent multi-seed, multi-arm, or cross-problem (`M3.1` CVRP/TSP/BPP, `M3.2` `B=36/100/200/400`) runs strictly one-by-one when they can run concurrently safely:
- **Subprocess Multiplexing:** Use `py -3.11 tools/multi_task_mux.py start|status|tail|wait|kill` (with `--max-concurrent` tuned to API rate limits) so each experiment shard runs with isolated stdout/stderr logs, independent SQLite WAL `PersistentRequestBudget`, crash recovery, and optional `--wt-panes` live split view in Windows Terminal (`wt`).
- **Thread/Process Pools & Worktrees:** Use `--workers N` inside batch runners or `git worktree` / parallel `codex-worker` subagents on strictly disjoint files when parallelizing code tasks.

## 3. Immutable Repository Redlines & Domain Invariants

- **Never modify** `eoh_frozen/`, `benchmarks/eohs_v1/`, prior published releases under `knowledge_store/releases/*`, or external blind custody stores (`.secrets/`, `C:\Users\24294\.agent_skill_custody\`). Keep `knowledge_store/current` as Git symlink mode `120000`.
- **No Blind / Select Leakage:** `dev_24`, `select_64`, and sealed blind suites must remain strictly role-isolated; never expose raw coordinates, demands, or `sealed_seed_token` in repo outputs or releases.
- **Cross-Problem & Statistical Discipline:** Keep online OBP (prefix invariance, zero future lookahead) strictly separated from offline BPP; dual-report `exact-k` vs free fleet and `common_completed` vs overall; never pool `3×120` seeded blind runs as 360 independent samples (report per-seed Paired Wilcoxon + 10k Bootstrap + Holm–Bonferroni).
- **Windows Test Command:** Always run `pytest` with `--basetemp=build/pytest-...` using `py -3.11` (or `C:\Users\24294\AppData\Local\Programs\Python\Python311\python.exe` if `py` is absent in a restricted sandbox), plus `validate_skill.py` and `knowledge_tools validate-release` before milestone commits.
