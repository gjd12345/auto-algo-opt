# M3.5 Architecture Specification (Rev 1.1, GPT-Audited): Four-Layer Auditable Memory, Anti-Anchoring Guardrails & KB Closed-Loop Promotion

**Status:** Hardened Design Approved (Audited against `main` @ `9bb0c046` by `gpt-6.2-sol` read-only red-team review; Python implementation deferred pending quota recovery & M5 completion)  
**Target Subsystem:** `agent_skill_loop/memory/`, `agent_skill_loop/session_memory.py`, `agent_skill_loop/session_contracts.py`, `agent_skill_loop/session_actions.py`, `agent_skill_loop/session_bridge.py`, `agent_skill_loop/evidence/`, `agent_skill_loop/file_lock.py`, `research_agent/` (`loop.py`, `tools/{session,kb,archive}_tools.py`), `knowledge_tools/`, `knowledge_store/`  
**Companion Obsidian Plan:** `03-进行中研究规划/2026-11-24｜M3.5系统设计：四层可审计记忆闭环、防锚定禁忌机制与知识库晋升架构.md`

---

## 1. Architectural Motivation & Verified Empirical Constraints

Inspection of `main` (`9bb0c046`) reveals three disconnected architectural pieces:
- `skills/algorithm-optimization/SKILL.md` documents memory-enabled session usage, Iteration B, and a 3+1 controller (though its text does not yet codify the full cross-session `A/B/C + Consolidation` contract).
- `agent_skill_loop/memory/api.py` implements `_SIDECAR_SCHEMA="algorithm-optimization-memory-sidecar/v2"` (`insight`/`solution` only, exact 5-key frontmatter, `_SECRET` filtering), `agent_skill_loop/session_memory.py` enforces `solution_threshold`, `evaluation_facts_sha256`, `candidate_code_sha256`, and `based_on` provenance, and `agent_skill_loop/evidence/memory.py` audits `compiled_into_context` / `omitted_at_gateway` / `gateway_attempt_exact_context`.
- However, `research_agent/tools/session_tools.py:100,286,371` hard-codes `memory_enabled=False`, `memory_basis=[]`, and `memory_action={"kind": "disabled"}`; `research_agent/loop.py:913–928` owns stagnation separately; `research_agent/tools/kb_tools.py` exposes only read-only retrieval from `knowledge_store/current`; and **flipping `memory_enabled=True` alone fails under `session_contracts.py:362–365`** (`disabled` mismatch) and leaves end-to-end retrieval/export un-owned.

Enabling naive memory is also empirically unsafe across six verified project findings:
1. **Static RAG Degradation (`archive/go-eoh-rag` @ `979fa766`, `rag_experiments_slides(1).pptx`):** Across 26 paired cells, 5-card framework RAG (`fwRAG`) scored **0 wins / 18 losses / 8 ties** vs `noRAG` (median paired `fwRAG - noRAG = +105.9977`; median vs `SA = +235.70135`, per `archive/fme-605/evidence/go_eoh_rag_20260705/framework_rag_cells.csv`). Separately, the `JoyAI-LLM-Pro` No-RAG pilot exposed constraint-hacking (`ratio=0.318` passing a `0.3` guard by omitting vehicle-count penalties, per `PILOT_FINDINGS.md:7–18`).
2. **Exploratory Cohort Non-Replication (`archive/research-loop-v2` @ `1d4608a8`, `archive/co-iteration-b` @ `74a1fb8b`):** In `research-loop-v2`, `85.05%` is an arithmetic decomposition of the `C−B` endpoint gap rather than causal attribution, and strict common-start forks (`750` evals) failed to replicate while `T2-C` (`0.038133 -> 0.037227`) matched premature anchoring patterns. In `co-iteration-b`, `G3` reflects 1 run/arm on 2 mini-heldout instances.
3. **Counterexample Over-Rejection vs Deterministic Case Savings (`wiki/concepts/反例误伤.md`, `记忆系统效果评估报告.pdf`):** Unscoped negative examples caused `97.6%` collateral rejection (`年糕` -> `糍粑`), whereas deterministic `rule-id` guards gained `+37.9pp` vs `-1.5pp` fuzzy hints, and `后处理代码拦截` reduced violations `10.3% -> 0%` with `38.7%` over-recall. Meanwhile, `记忆系统效果评估报告.pdf` (`N=1` observed same-task case study) showed `52.02%` Easy (`$4.21->$2.02`) and `39.60%` Hard (`$4.04->$2.44`, Edit `13->1`) cost reduction when task invariants match identically.
4. **In-Loop Reflection & Live Progress/Deduplication Bugs (`RQ1b-v2`, `D0–D32`, `search_progress.py`):** In `RQ1b-v2` (`804` logical reqs / `809` HTTP attempts), Arm C valid candidates dropped **`87.50% -> 82.03%`** (`112/128` vs `105/128`), `strict_supported_C_traces = 0`, `same_code_behavior_accuracy_delta = -0.009259`, and `median_target_penalized_loss_reduction = -0.192083`. In `main` code, both `B01` and `B02` are **confirmed live bugs**.
5. **Truth-Source Drift & Context Inflation (`.mnemon/`, `archive/memory-recovery` @ `27442cb7`, `FGSE arXiv:2611.14326`, `STALE arXiv:2605.06527`):** `memory-recovery` curbed a `1,543,202`-token raw JSON blowup using structured historical briefs (`16,000`-char controller cap in `tools/memory_content_brief.py`), while `.mnemon/` exposed 4-truth-source drift ("51 healthy memories != usable").

---

## 2. Four-Layer Architecture, Ownership & L3 Trust Boundaries

1. **L0 · Ephemeral Trajectory Working Memory (`archive_tools.py` + `research_agent/loop.py`):** Holds intra-run Pareto archive, `compute_weakest_regimes_feedback`, stagnation state (`loop.py:913–928`), AST hashes, and typed `n=200` latency telemetry. Restored strictly within a single run directory; never leaks across arms.
2. **L1 · Episodic Insights & Scoped Antipatterns (Sidecar-v3 `insight` / `antipattern`):** Every `antipattern` MUST declare typed compatibility predicates (`problem`, `interface_id`, `fleet_policy`, `evaluator_version`, `n_range`, `budget_ms_range`) + `## Guardrail & False-Positive Boundary` + bounded TTL/expiry and re-entry rule. No `eval` of card strings—only typed matcher evaluation.
3. **L2 · Verified Procedural Solutions (Sidecar-v3 `solution`):** Stores executable algorithm transformations whose **claimed mechanism is bound to verified AST/code delta, parent candidate, evaluator version, and interface**, passing `> solution_threshold` (with `>=` edge explicitly defined), `evaluation_facts_sha256`, and fixed `B01`.
4. **L3 · Immutable Domain Knowledge Store (`knowledge_store/current`) [P0 Trust Boundary Hardened]:**
   - **No Blind Oracle Leakage (P0-1):** Build and promote L3 cards strictly from authorized **dev** evidence BEFORE locking candidate, roster, and release digest. Keep `select` in its authorized selection role. **Blind-derived outcomes, pass/fail flags, and availability decisions MUST NEVER influence L3 publication, activation, or Arm 3 visibility** (verify by mutating synthetic blind outcomes and proving release bytes, activation, and retrievable cards stay bit-identical).
   - **Pinned Provenance & No Override Hijacking (P0-2):** Pin an approved `release_id` and `manifest_digest` in each arm's manifest; validate resolved release files inside `kb_tools.py` / `knowledge_tools/core.py` against that pinned root; prohibit symlinks/reparse points inside release contents; enforce matching resume digest on restart; and restrict `knowledge_tools` release activation strictly to the offline publisher (keeping `knowledge_store/current` at Git mode `120000` and prior releases untouched).

**End-to-End Component Ownership (P1-2):** Before coding begins, assign explicit interfaces for (a) session initialization / `Context-Pack` injection (`session_tools.py` + `session_bridge.py`), (b) per-round stagnation triggers (`research_agent/loop.py` + `session_actions.py`), (c) L0 state restoration across pause/resume (`archive_tools.py`), and (d) hard Arm 0 isolation (`memory_enabled=False` AND `kb_tools` disabled/zero-exposure on both memory and KB surfaces).

---

## 3. Code-Verified Defect Fixes & Sidecar-v3 Upgrade Contract

### 3.1 Verified Live Code Defects in `main` (`9bb0c046`)
- **Fix `B01` (Confirmed Live at `agent_skill_loop/evidence/search_progress.py:458–464` & `session_actions.py:1021–1026`):** Currently `absolute_gain >= 0` (`>= min_absolute_gain`) with `relative_gate=None` when `first in (None, 0.0)` allows `0->0` and `1->1` zero-gain trajectories to pass as `"progress"`, skipping stagnation gates. **Patch:** Require strict direction-correct positive margin `> precision_floor` for named evaluator precision, define explicit `first == 0` verified-zero-reference absolute-only rules vs missing evidence (`first is None`), and fail equality/negative/sub-resolution moves. *(Pin exact upstream precision floor rule before adopting any rounding constant.)*
- **Fix `B02` (Confirmed Live at `agent_skill_loop/evidence/search_progress.py:141–164, 167–195`):** Both `_source_metrics` (using `code_sha256`, NOT AST) and `_behavior_metrics` preload same-round non-originals (`not _generated(item)`, i.e. repairs) into `seen` before iterating originals. **Patch:** Attribute source (`code_sha256`) and behavior novelty strictly in durable **attempt order** across originals and repairs without retroactive preloading.
- **Fix `B03` (Split Two-Gateway Contract Across `tools/memory_content_controller_call.py:56–106`, `tools/memory_content_brief.py:11,158–160`, `session_contracts.py:15,775–797`, `evidence/memory.py:64–110`, `session_bridge.py:920–928`):** Separate three distinct budgets cleanly: (1) historical brief char cap (`16,000` chars), (2) Session serialized UTF-8 byte & char advisory packing (`<=12,000` chars / explicit UTF-8 byte limit covering multibyte CJK + non-memory prompt overhead), and (3) complete-request token ceiling (`30k/6k` enforced *pre-dispatch*, not post-hoc). Decouple transport `attempted_send` vs HTTP response `delivered` in `session_bridge.py:920–928` so crashes between marker write and `POST` do not misreport delivery.
- **Fix `R07` (`agent_skill_loop/session_actions.py:929–957`, `session_memory.py:35–93`, `memory/api.py:344–413`):** Preserve `memory-revise`'s core contract: **allow** same-round format/heading repairs against unchanged `evaluation_facts_sha256`, while binding `old_proposal_sha256`, `new_proposal_sha256`, `evaluation_facts_sha256`, and expected CAS `card_head`; require newly verified evidence **only** when factual claims/deltas change. Separate per-operation lock (`session_memory.py:12–21`) from same-card CAS (`memory/api.py`).

### 3.2 Sidecar-v3 Rollout & Crash-Safe Publication (`P1-1`, `P1-9`, `P2-2`)
Inspection of `agent_skill_loop/memory/api.py:24–59,305–425` and `session_contracts.py:249–255,355–365` shows strict equality checks (`version == 2`, `_FILE`/`_REFERENCE` regexes `insight|solution` only, exact 5 frontmatter keys, `len(memory_basis) <= 2`). Therefore M3.5 mandates a **synchronized dual-reader migration**:
1. Update `api.py` (`format_version in {2, 3}`, `_SIDECAR_SCHEMA` v2/v3 dual support, `_FILE` / `_REFERENCE` supporting `antipattern`, optional structured v3 metadata), `session_contracts.py` (`MEMORY_ACTION_TYPES`, raising `memory_basis` cap from `2` to `>=3` when injecting 1 insight + 1 antipattern + 1 solution, and fixing `enabled`/`disabled` gate), and `session_actions.py` together. Verify legacy, v2, and v3 round-trips plus quarantined/superseded card rejection and older-reader behavior.
2. **Eliminate Two-File Orphan Window (`P2-2`):** Currently `api.py:420–425` writes `.json` sidecar before `.md`, creating an orphan crash hazard. Use a single recoverable commit unit or transactional orphan recovery on startup under `agent_skill_loop/file_lock.py` (which uses `msvcrt.locking` on Windows and `fcntl.flock` on POSIX—keeping lock pathnames consistent everywhere).
3. **OS-Enforced Permission Boundary (`P1-9`):** Treat memory cards strictly as untrusted advisory text; reject `eval` in scope predicates; run all generated candidates inside existing validation gates under restricted OS worker permissions (no access to network, credentials, or out-of-scope filesystem roots).

---

## 4. Anti-Anchoring, Scoped Antipatterns & Offline `Auto-Dream`

1. **MMR & Scoped Cooldown (`P1-7`):** Balance relevance against AST similarity, cap active `solution` cards to **<= 1** per pack, and scope cooldown strictly to **observed, attributable evaluations** matching `(problem, interface_id, fleet_policy, evaluator_version)` — never trigger cooldown from `HTTP 429` or unevaluated crashes. Add automatic expiry & re-entry; compute false-trigger rate **per regime** on held-out valid examples (flag insufficient evidence when sparse); and maintain hard separation keeping **offline BPP evidence out of online OBP admission** (OBP prefix-invariance checked separately).
2. **Typed Evidence Manifest in `Auto-Dream` (`P1-8`):** Replace pure prose-length `BODY_SHRINK_THRESHOLD = 0.7` (which can pass by retaining filler text while dropping regime/negative caveats) with a **typed claim-to-evidence manifest** requiring preservation of scope conditions, denominators, adverse results, contradictions, and source references, plus compatible `(interface_id, evaluator_version)` checks before AST clustering. Account for offline LLM tokens separately (never advertise offline consolidation as zero-cost).

---

## 5. Mandatory Evaluation Protocol (Frozen 4-Arm Common-Start Fork, `P1-10`)

To eliminate confounding seen in historical `research-loop-v2` and `agent_go`:
- **Pre-Freeze Identity:** Freeze identical fork manifests across all 4 arms for initial population, incumbent, useful starting state, checkpoint, request/time budget, model/gateway settings, and initial L3/L1/L2 digests; isolate mutable per-arm stores; randomize launch order; apply the same transport safety ceiling across all arms; include a matched-cap control for mechanism claims; pre-register primary contrasts, Holm-Bonferroni families, completion handling, and inference unit.
- **Four Arms:** **Arm 0** (M5 ON, `memory=OFF`, KB isolated), **Arm 1** (Naive static/unscoped memory within shared transport safety ceiling), **Arm 2** (M3.5 L1+L2 + scoped `antipattern` + MMR + cooldown, `Auto-Dream` OFF), **Arm 3** (Full M3.5 dev-promoted L0–L3 + offline `Auto-Dream` — strictly blind-isolated).
- **Reporting:** Assert `feature_count > 0` & gateway `memory_consumption.json` wiring; report per-seed Paired Wilcoxon + 10k paired bootstrap + Holm-Bonferroni for both overall and `common_completed`, keeping `exact-k` vs `free_fleet` strictly separate and never pooling `3×120` into 360.

---

## 6. Recovered GitHub Contracts & Red-Team Audit Closure

### 6.1 Reconciled Contracts from `gjd12345/agent_go` & `codex-skills-sync`
- **Outcome-Weighted RAG (`experiment/rag-ablation-4arm@b22f234`, exploratory):** 24-run JoyAI `gen=4` matrix (2 problems × 4 arms × 3 repeats) showed exploratory CVRP signal (`A_pure 13.519 -> B_keyword 13.126 -> C_keyword_outcome 12.715`, `+5.95%` median; `3/3` wins give minimum two-sided sign-test $p=0.25$ — exploratory only), while `D` was invalidated (`rag_population_feature_count=0`) and `68` (`1f5af0a0`) vs `104` (`e26d6133`) outcome snapshots must be pinned by digest.
- **Vocab Isolation (`CARD_SYNTHESIS_SPEC.md`), TOCC 10-Mode Triage, `evidence-labeling` & `PoolAPI` Cold-Start Guard (`total < 3 -> 1.0`):** Integrated into Sidecar-v3 schemas and runtime gates (replacing POSIX-only `fcntl.flock` with `file_lock.py`). *(Skill count reconciled from `codex-skills-sync/README.md` = 58 documented core skills vs 56 top-level dirs under `skills/`.)*

### 6.2 `gpt-6.2-sol` Red-Team Audit Summary (`task_092f3ece21c4`, Read-Only)
All **2 P0**, **16 P1**, and **5 P2** findings returned by `gpt-6.2-sol` were verified against source files (`api.py`, `session_contracts.py`, `session_actions.py`, `search_progress.py`, `file_lock.py`, `framework_rag_cells.csv`, `PILOT_FINDINGS.md`, `clean_summary.md`, `selected_repeat_summary.md`, `b4_intron_ablation.md`, `rq1b_v2_resume_delivery_20260831.json`, `A-B-C实验学术分析报告.md`). Zero false positives were found; every verified spec contract fix (P0-1/2, P1-1..10, P2-1..3) and statistical scoping correction (P1-11..16, P2-4..5) has been incorporated into this Rev 1.1 specification before any M3.5 code implementation begins.

---

## 7. Immutable Redlines

- Never modify `eoh_frozen/`, `benchmarks/eohs_v1/`, published `knowledge_store/releases/*`, or external blind custody stores (`.secrets/`, `C:\Users\24294\.agent_skill_custody*`).
- Keep `knowledge_store/current` as Git symlink mode `120000`.
- Never expose raw coordinates, demands, `sealed_seed_token`, or blind-derived promotion decisions inside `L1/L2/L3` memory cards or `Auto-Dream` logs.
