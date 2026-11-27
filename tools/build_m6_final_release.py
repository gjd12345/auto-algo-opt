"""Build the immutable Milestone 6 Waves 1–4 knowledge release.

Sync seven reviewed cards from the experiment reports, validate the workspace,
rebuild the dashboard with the M5 workbench assets, and activate the verified release.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from frontend.build_dashboard import build_dashboard
from knowledge_tools.core import (
    activate_verified_release,
    build_release,
    read_json,
    sha256_bytes,
    sha256_file,
    validate_workspace,
    write_json,
)

M5_RELEASE_ID = "20261125-main-co-workbench-m5-final"
M6_RELEASE_ID = "20261127-main-co-workbench-m6-final"
M6_SOURCE_ID = "src-milestone6-waves1to4-closure-20261127"

W1 = "experiments/milestone6_wave1_clean_audit"
W2 = "experiments/milestone6_wave2_c2_b1"
W3 = "experiments/milestone6_wave3_c1_exact_k"
W4 = "experiments/milestone6_wave4_b2_b3"
W1_SUMMARY = f"{W1}/wave1_master_summary.json"
W1_THEORY = f"{W1}/wave1_theoretical_abstraction_verified.json"
C2_OFFLINE = f"{W2}/c2_offline/c2_offline_430_report.json"
B1_EVAL = f"{W2}/eval/b1_eval_report.json"
W2_THEORY = f"{W2}/wave2_theoretical_abstraction_verified.json"
C1_OFFLINE = f"{W3}/c1_offline/c1_offline_430_report.json"
C1_EVAL = f"{W3}/eval/c1_eval_report.json"
W3_THEORY = f"{W3}/wave3_theoretical_abstraction_verified.json"
C1_TIGHTNESS = f"{W3}/wave3_tightness_feasibility_theory_verified.json"
B2_ATTEMPT1 = f"{W4}/b2_sandbox_pilot_attempt1/b2_pilot_audit.json"
B2_PILOT = f"{W4}/b2_sandbox/b2_pilot_audit.json"
B2_EVAL = f"{W4}/b2_sandbox/b2_evaluation.json"
B3_ROSTER = f"{W4}/b3_memory_kb/b3_fork_roster.json"
B3_EVAL = f"{W4}/b3_memory_kb/b3_evaluation.json"
W4_THEORY = f"{W4}/wave4_theoretical_abstraction_verified.json"

W1_RUNNER = "tools/run_m6_wave1_clean_audit.py"
W2_RUNNER = "tools/run_m6_wave2_c2_b1.py"
W3_RUNNER = "tools/run_m6_wave3_c1_exact_k.py"
W4_RUNNER = "tools/run_m6_wave4_b2_b3.py"
ABP = "cvrp_ext_cvrplib_abp_74"
SET_X = "cvrp_ext_cvrplib_x_100"
OFFICIAL_OR = "official_or_174"


@dataclass(frozen=True)
class Card:
    entry_id: str
    title: str
    summary: str
    method: str
    findings: str
    limits: str
    reports: tuple[str, ...]
    artifacts: tuple[str, ...]
    tags: tuple[str, ...]
    entry_type: str = "evidence"
    category: str = "evidence"
    paradigm: str = "ruin_and_recreate"
    knowledge_tier: str = "verified_experiment"


def _head_short_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO, text=True, stderr=subprocess.DEVNULL,
        ).strip() or "main"
    except (OSError, subprocess.CalledProcessError):
        return "main"


def _pin(rel_path: str, commit: str) -> dict[str, Any]:
    try:
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain", "--", rel_path],
            cwd=REPO,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        dirty = ""
    pin = {
        "kind": "repo_code",
        "commit": "worktree" if dirty else commit,
        "path": rel_path,
        "sha256": sha256_file(REPO / rel_path),
    }
    if dirty:
        pin["worktree_base_commit"] = commit
    return pin


def _ensure_source(workspace_dir: Path, reports: dict[str, Any]) -> None:
    src_path = workspace_dir / "sources.json"
    doc = read_json(src_path)
    source = {
        "id": M6_SOURCE_ID,
        "title": "Milestone 6 Waves 1–4 experimental closure and verified theoretical framework",
        "authors": ["auto-algo-opt research log"],
        "year": 2026,
        "venue": "Internal experimental audit and immutable knowledge release",
        "doi": None,
        "url": f"https://github.com/gjd12345/auto-algo-opt/blob/main/{W4_THEORY}",
        "kind": "internal_experiment_report",
        "accessed_on": "2026-11-27",
        "availability": "local_repository",
        "license": "repository-internal research record",
        "selected": True,
        "selection_reason": (
            "Covers the clean deadline audit, geometry–scale screening, decoupled search controls, "
            "Exact-K feasibility, diagnostic sandbox ablation, and gated memory transfer."
        ),
        "locator": "; ".join(reports),
        "read_depth": "full_text_local",
        "notes": "The reports retain separate fleet and timing endpoints and preserve within-seed pairing.",
    }
    sources = doc["sources"]
    for index, item in enumerate(sources):
        if item["id"] == M6_SOURCE_ID:
            sources[index] = source
            break
    else:
        sources.append(source)
    write_json(src_path, doc)


def _write_card(entries_dir: Path, card: Card, pins: dict[str, dict[str, Any]]) -> None:
    sources = "\n".join(f"- `{path}`" for path in card.reports)
    artifacts = "\n".join(f"- `{path}`" for path in card.artifacts)
    body = f"""# {card.title}

{card.summary}

## 定义或方法步骤

{card.method}

## 适用条件、假设与限制

{card.limits}

## 来源及支持的具体结论

{card.findings}

{sources}

## 代码和评测关联

{artifacts}

## 未确认项与冲突证据

The paired contrasts apply to their recorded suites, endpoints, and seeds. Blind instances repeated across seeds do not constitute independent replicates.
"""
    md_bytes = body.encode("utf-8")
    (entries_dir / f"{card.entry_id}.md").write_bytes(md_bytes)
    write_json(entries_dir / f"{card.entry_id}.json", {
        "id": card.entry_id,
        "type": card.entry_type,
        "title": card.title,
        "category": card.category,
        "problem_family": "cvrp",
        "tags": ["cvrp", "milestone-6", *card.tags],
        "status": "reviewed",
        "summary": card.summary,
        "attributes": {
            "knowledge_tier": card.knowledge_tier,
            "problem_variant": "standard_cvrp",
            "paradigm": card.paradigm,
            "artifact_refs": [pins[path] for path in card.artifacts],
        },
        "relations": {
            "problems": ["problem-cvrp", "problem-lit-cvrp-large"],
            "methods": ["method-cvrp-m3-ruin-recreate-l3", "method-research-agent-m3-autonomous-loop"],
            "sources": [M6_SOURCE_ID],
        },
        "source_refs": [M6_SOURCE_ID],
        "evidence_refs": [f"report:{path}" for path in card.reports],
        "code_refs": [],
        "content_sha256": sha256_bytes(md_bytes),
    })


def _completion(stats: dict[str, Any]) -> str:
    return f"{stats['returned_before_deadline_completed_count']}/{stats['n_instances']}"


def _wave1(summary: dict, theory: dict) -> Card:
    a1, a2, a4 = (summary[key] for key in ("a1_highlights", "a2_highlights", "a4_highlights"))
    verified = theory["wave1_propositions_verified"]
    anomaly = verified["a1_reevo_anomaly"]
    factorial = verified["a3_factorial_effects"]
    groups = list(summary["a3_highlights"])
    divergence = verified["a2_m2_h4a_divergence_share_pct"]
    timing = [
        f"| {deadline} | `{solver}` | {stats['completed_count']}/{stats['n_instances']} | "
        f"{stats['solve_ms_p50']:.2f} | {stats['solve_ms_p95']:.2f} | {stats['censored_count']} |"
        for deadline, solvers in a4["m32_set_x_nocontention_focus"].items()
        for solver, suites in solvers.items()
        for stats in (suites["430_free_fleet"],)
    ]
    parity = "\n".join(
        f"- `{case}` matched on {stats['common_completed_count']} common completions "
        f"with maximum absolute objective difference {stats['max_abs_diff']:g}."
        for case, stats in a4["golden_parity"].items()
    )
    parts = ", ".join(part.upper() for part in summary["completed_parts"])
    return Card(
        entry_id="evidence-m6-wave1-clean-audit-20261127",
        title="M6 Wave 1 · Clean deadline audit and no-contention wall timings",
        summary=(
            f"The {parts} audit found {a1['uncensored_overrun_anomalies_count']} uncensored overruns and "
            f"{a1['censored_callback_overrun_total']:,} censored callback overruns. At 25 ms the "
            f"strict common-completed counts were {a2['m2_25ms_strict_common']} for M2 and "
            f"{a2['m3_25ms_strict_common']} for M3."
        ),
        method=(
            "Record `feasible_before_deadline` when a valid incumbent is observed by the deadline and "
            "`returned_before_deadline` when a valid solution is actually delivered by the deadline. "
            "For M3.2, cross training and evaluation deadlines in a 2×2 factorial at a fixed request cap. "
            f"The audit reports separate contrasts for {', '.join(groups)}."
        ),
        findings="\n".join([
            f"- A1 corrected a ReEvo boundary case at {anomaly['solve_ms']:.4f} ms from "
            f"{anomaly['old']:.6f} to a strict penalized score of {anomaly['clean']:.6f}.",
            f"- A2 attributes {divergence:.4f}% of the M2 H4A overall gain to completion divergence.",
            "- A3's verified blind free-fleet example gives average training and evaluation effects of "
            f"{factorial['2_alpha_avg_train']:+.4f} and {factorial['2_beta_avg_eval']:+.4f}, "
            f"with interaction {factorial['4_gamma_interaction']:+.4f} and diagonal "
            f"contrast {factorial['diagonal_diff']:+.4f}.",
            parity,
            "",
            "| Deadline | M3.2 solver | Strict free-fleet completion | Solve p50 (ms) | Solve p95 (ms) | Censored |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
            *timing,
        ]),
        limits=(
            "A4 uses no-contention wall timings. Censored observations are recorded at the observed cutoff "
            "and give lower bounds on full solve time. Keep common-completed route quality separate from "
            "the overall penalized comparison, which incorporates delivery failures."
        ),
        reports=(W1_SUMMARY, W1_THEORY),
        artifacts=(W1_RUNNER, "tools/run_external_baselines_2026.py"),
        tags=("deadline-audit", "factorial-ablation", "wall-timing"),
    )


def _wave2_c2(report: dict, theory: dict) -> Card:
    baseline = report["baseline"]
    audited = theory["c2_verification"]
    budgets = sorted(report["budgets_ms"].items(), key=lambda item: int(item[0]))
    table = [
        f"| {ms} | `{arm}` | {_completion(stats)} | "
        f"{_completion(budget['exact_k']['solvers'][arm])} |"
        for ms, budget in budgets
        for arm, stats in budget["free_fleet"]["solvers"].items()
    ]
    comparisons = "; ".join(
        f"{ms} ms: {_completion(budget['free_fleet']['solvers']['cw_static'])} for `cw_static` "
        f"and {_completion(budget['free_fleet']['solvers'][baseline])} for `{baseline}`"
        for ms, budget in budgets
    )
    return Card(
        entry_id="evidence-m6-wave2-c2-multiscale-430-20261127",
        title="M6 Wave 2 C2 · Geometry–scale probing and strict returns",
        summary=f"C2 strict free-fleet returns on the external {report['n_instances']}-instance panel ({comparisons}).",
        method=(
            "Probe joint geometry and scale regimes when screening candidates. The offline benchmark reports "
            f"strict free-fleet delivery and Exact-K scoring separately. Its Exact-K procedure is "
            f"`{report['exact_k_method']}`."
        ),
        findings="\n".join([
            "| Deadline (ms) | Solver | Strict free-fleet returns | Strict Exact-K returns |",
            "| ---: | --- | ---: | ---: |",
            *table,
            "",
            f"`cw_static` tied the baseline on {audited['cw_static_ties_on_common_500ms']} common "
            f"completions at 500 ms and {audited['cw_static_ties_on_all_2000ms']} at 2000 ms. "
            f"The missed baseline instances accounted for {audited['missed_share_pct']:.4f}% "
            "of the verified 500 ms total objective difference.",
        ]),
        limits=(
            "The common-completed comparison measures route quality on pairs that returned. The overall "
            "penalized comparison also reflects which solvers returned. A measured probe covers its tested "
            "regime. A deadline guarantee requires a sound runtime bound or a guarded fallback."
        ),
        reports=(C2_OFFLINE, W2_THEORY),
        artifacts=(W2_RUNNER, "agent_skill_loop/interface_design/multiscale.py"),
        tags=("geometry-scale", "multiscale-screening", "strict-returns"),
    )


def _wave2_b1(report: dict, theory: dict) -> Card:
    points = report["points"]
    baseline = report["paired_baseline"]
    risk_arm = "risk_bounded_adaptive_stop"
    arms = list(dict.fromkeys(point["arm"] for point in points))
    baseline_by_seed = {point["seed"]: point for point in points if point["arm"] == baseline}
    stopped = [point for point in points if point["arm"] == risk_arm]
    savings = mean(
        1 - point["requests_used"] / baseline_by_seed[point["seed"]]["requests_used"]
        for point in stopped
    )
    verified = theory["b1_verification"]
    regret = verified["signed_blind_regret_pct_by_seed"]
    rows = [
        f"| {point['seed']} | {baseline_by_seed[point['seed']]['requests_used']} | {point['requests_used']} | "
        f"{regret[str(point['seed'])]:+.5f}% |"
        for point in stopped
    ]
    frontier = report["pareto_frontier"]
    frontier_rows = [
        f"- `{point['arm']}` (seed {point['seed']}) used {point['requests_used']} requests and "
        f"scored {point['blind_120_quality']:.5f}."
        for point in frontier
    ]
    return Card(
        entry_id="evidence-m6-wave2-b1-decoupled-pareto-20261127",
        title="M6 Wave 2 B1 · Decoupled early stop and basin restart",
        summary=(
            f"The {len(arms)}-arm audit records {savings:.1%} mean request savings for the risk-bounded "
            f"stop arm and {len(frontier)} empirical Pareto points in request spend and blind loss. "
            f"Mean signed blind regret was {mean(regret.values()):+.4f}%."
        ),
        method=(
            "Compare " + ", ".join(f"`{arm}`" for arm in arms) + ". "
            "A global stop ends the request trajectory. A basin restart changes the continuation "
            "policy while preserving the remaining budget and incumbent. The blind objective is "
            f"`{report['blind_120_quality_metric']}`."
        ),
        findings="\n".join([
            "| Seed | Baseline requests | Risk-bounded requests | Signed blind regret |",
            "| --- | ---: | ---: | ---: |",
            *rows,
            "",
            f"Pareto points at a {report['budget_ms']} ms evaluation deadline",
            "",
            *frontier_rows,
            "",
            f"The theory audit reproduced {verified['replayed_stopping_decisions_matched']} logged stopping decisions.",
        ]),
        limits=(
            "With a valid bound q on the conditional probability of improvement and a bound M on its "
            "conditional magnitude given improvement, the expected remaining gain is at most qM. "
            "Those bounds depend on the continuation policy. The seed-level blind regret is empirical."
        ),
        reports=(B1_EVAL, W2_THEORY),
        artifacts=(W2_RUNNER, "research_agent/loop.py"),
        tags=("early-stop", "basin-restart", "pareto-frontier"),
    )


def _wave3(offline: dict, evaluation: dict, theory: dict, tightness: dict) -> Card:
    arm = "Y_11"
    seeds = evaluation["by_seed"]
    reference = {
        (str(run["seed"]), str(int(run["budget_ms"]))): run
        for run in offline["pyvrp_dual_endpoint_reference"]["runs"].values()
    }
    rows = []
    for seed, result in sorted(seeds.items()):
        for ms, budget in result["budgets_ms"].items():
            groups = budget["groups"]
            abp, set_x, official = (groups[key]["exact_k"]["solvers"][arm] for key in (ABP, SET_X, OFFICIAL_OR))
            free = groups[OFFICIAL_OR]["free_fleet"]["solvers"][arm]
            pyvrp = [
                reference[seed, ms][endpoint]["aggregates"]["true_or_174_exact_k"]
                for endpoint in ("feasible_before_deadline", "returned_before_deadline")
            ]
            rows.append(
                f"| {seed} | {ms} | {_completion(abp)} | {_completion(set_x)} | {_completion(official)} | "
                f"{_completion(free)} | {pyvrp[0]['completed_count']}/{pyvrp[0]['n_instances']} | "
                f"{pyvrp[1]['completed_count']}/{pyvrp[1]['n_instances']} | {budget['acceptance']['passed']} |"
            )

    witness = theory["proposition_4_capacity_witness_and_counterexamples"]
    aggregate = witness["aggregate_capacity_counterexample"]
    ffd = witness["ffd_incompleteness_counterexample"]
    calibrated = tightness["calibration_430"]["500"]
    strata = [
        f"- `{label}`: {row['y00_overshoots']}/{row['n']} Y_00 fleet overshoots."
        for label, row in calibrated["high_rho_by_delta"].items()
    ]
    return Card(
        entry_id="evidence-m6-wave3-c1-exact-k-contract-20261127",
        title="M6 Wave 3 C1 · Fleet-aware construction and the Exact-K contract",
        summary=(
            "The clean C1 seed-level comparison records Y_11 strict Exact-K returns on ABP, Set X, "
            "and the official OR panel alongside PyVRP's feasible-incumbent and strict-return endpoints. "
            f"The offline gate reported passed={offline['passed']} and evolved evaluation reported "
            f"passed={evaluation['passed']}."
        ),
        method=(
            "A solution must cover each customer once, respect capacity Q on each route, and deliver "
            "exactly K nonempty routes before the deadline to count under Exact-K. Let rho be total "
            "demand divided by KQ and delta_max be the maximum demand divided by Q. Bounds "
            "rho ≤ 1 and delta_max ≤ 1 are necessary. A feasible partition into K routes is a witness. "
            "If the two smallest current route loads sum to more than Q, whole-route merges are blocked "
            "and achieving K may require exchanging or repacking customers."
        ),
        findings="\n".join([
            "| Seed | Deadline (ms) | Y_11 ABP Exact-K | Y_11 Set X Exact-K | Y_11 OR Exact-K | "
            "Y_11 OR free fleet | PyVRP OR exact feasible | PyVRP OR exact returned | Y_11 gate passed |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
            *rows,
            "",
            f"Synthetic aggregate-capacity witness of insufficiency: demands {aggregate['q']} with "
            f"Q={aggregate['Q']} and K={aggregate['K']} need {aggregate['ffd_bins']} routes. "
            f"For demands {ffd['q']} with Q={ffd['Q']} and K={ffd['K']}, first-fit decreasing uses "
            f"{ffd['ffd_bins']} routes despite a feasible K-route packing.",
            "",
            "In the highest rho stratum of the 500 ms calibration, the observed overshoots vary with "
            "the maximum demand share:",
            "",
            *strata,
        ]),
        limits=(
            theory["proposition_2_factorial_interaction"]["causal_scope_p1_verified"]
            + " A miss with a validated K-route witness shows a construction or return failure on a feasible case."
        ),
        reports=(C1_OFFLINE, C1_EVAL, W3_THEORY, C1_TIGHTNESS),
        artifacts=(W3_RUNNER, "agent_skill_loop/interface_design/fleet_exact_k.py"),
        tags=("exact-k", "fleet-repair", "capacity-tightness"),
    )


def _script_rate(audit: dict, precision: int) -> str:
    return (
        f"{audit['valid_scripts']}/{audit['scripts_executed']} "
        f"({audit['valid_script_execution_rate']:.{precision}%})"
    )


def _wave4_b2(attempt: dict, pilot: dict, report: dict, theory: dict) -> Card:
    full = report["sandbox_rates"]
    examples = theory["wave4_theorems"]["W4-1"]["observed"]["free_fleet_common_completed_relative_gain_pct_examples"]
    contrasts = []
    for example in examples:
        lower, upper = example["bootstrap_ci95_pct"]
        contrasts.append(
            f"- {example['suite']}, {example['model']}, seed {example['seed']}, {example['contrast']} "
            f"gave {example['gain_pct']:+.4f}% common-completed gain "
            f"(paired bootstrap 95% CI {lower:+.4f}% to {upper:+.4f}%, "
            f"Holm-adjusted Wilcoxon p={example['wilcoxon_p_holm']:.8f})."
        )
    completions = [
        f"- `{suite}`: {min(rates):.0%} to {max(rates):.0%} strict free-fleet completion "
        f"across {len(rates)} cells."
        for suite, data in report["suites"].items()
        for rates in ([cell["free_fleet"]["completion_rate"] for cell in data["per_cell"].values()],)
    ]
    return Card(
        entry_id="evidence-m6-wave4-b2-clean-sandbox-20261127",
        title="M6 Wave 4 B2 · Clean numerical sandbox ablation",
        summary=(
            f"Valid script execution went from {_script_rate(attempt['overall'], 1)} in the first pilot "
            f"to {_script_rate(pilot['overall'], 0)} in the hardened pilot and {_script_rate(full, 2)} "
            f"in the full {full['cell_count']}-cell ablation. The full audit recorded "
            f"gate_bypass_count={full['gate_bypass_count']}."
        ),
        method=(
            "Compare free tool choice, slice-only diagnostics, and sandbox-only diagnostics at a "
            f"{report['deadline_ms']:g} ms evaluation deadline. Count scripts as valid after successful "
            "execution with verified finite numeric evidence. Report script validity, diagnostic-round "
            "completion, and routing outcomes at their respective denominators."
        ),
        findings="\n".join([
            f"The full ablation verified {full['diagnostic_rounds_completed']}/{full['diagnostic_rounds_required']} "
            f"required diagnostic rounds. {full['success_cells']}/{full['cell_count']} cells had a valid script.",
            "",
            *completions,
            "",
            *contrasts,
        ]),
        limits=(
            f"The first and hardened pilots recorded {attempt['overall']['gate_bypass_count']} and "
            f"{pilot['overall']['gate_bypass_count']} gate bypasses, respectively. Their mixes of script "
            "attempts could differ. The seed-level intervals show effects in both directions and "
            "the experiment did not specify an equivalence margin. The Set X Exact-K endpoint is null."
        ),
        reports=(B2_ATTEMPT1, B2_PILOT, B2_EVAL, W4_THEORY),
        artifacts=(W4_RUNNER, "research_agent/tools/math_sandbox.py"),
        tags=("sandbox-ablation", "diagnostic-evidence", "seed-level-contrasts"),
    )


def _wave4_b3(roster: dict, report: dict) -> Card:
    set_x = report["suites"][SET_X]
    cells = roster["roster"]
    audits = report["memory_kb_audit"]
    attributed = sum(audits[cell]["attribution_valid"] is True for cell in cells)
    arm = "arm_b3_2_offline_l3_c2_gated"
    completion = [set_x["per_cell"][cell]["free_fleet"]["completed_count"] for cell in cells]
    expected = report["set_x_expected_completed"]
    transfers = [check for check in report["negative_transfer_checks"] if check["suite_id"] == SET_X]
    offline = [check for check in transfers if check["cell"].endswith(f"/{arm}")]
    clean = sum(check["negative_transfer"] is False for check in offline)
    rows = []
    for check in transfers:
        model, seed, treatment = check["cell"].split("/")
        delta = check["common_completed_mean_treatment_minus_control"]
        delta_text = f"{delta:+.2f}" if delta is not None else "unavailable"
        rows.append(
            f"| {model} | {seed} | `{treatment}` | {check['common_completed']}/{check['denominator']} | "
            f"{delta_text} | {check['negative_transfer']} |"
        )

    return Card(
        entry_id="evidence-m6-wave4-b3-clean-memory-kb-20261127",
        title="M6 Wave 4 B3 · Unified-base KB and C2-gated memory transfer",
        summary=(
            f"{attributed}/{len(cells)} forked cells had attribution_valid=True and the audit recorded "
            f"{len(report['hard_alarms'])} hard alarms. Set X strict free-fleet completions per cell ranged "
            f"from {min(completion)}/{expected} to {max(completion)}/{expected}. "
            f"`{arm}` avoided observed negative transfer in {clean}/{len(offline)} Set X seeds."
        ),
        method=(
            f"Start all arms from the pinned base KB `{roster['base_kb']['release_id']}`. Compare base KB only, "
            "online writeback, frozen offline L3 with C2, and full closed-loop memory with C2. The report "
            f"evaluates at {report['deadline_ms']:g} ms and flags negative transfer for lower strict "
            "completion or a higher mean objective on common-completed pairs against the base arm."
        ),
        findings="\n".join([
            "| Model | Seed | Set X treatment | Common-completed pairs | Mean treatment minus base | Negative transfer |",
            "| --- | --- | --- | ---: | ---: | --- |",
            *rows,
        ]),
        limits=(
            "Set X parity is a free-fleet result and the report's Set X Exact-K endpoint is null. "
            "The experiment holds the base KB fixed. Identifying the separate contributions of screening, "
            "tags, and gateway attribution would require additional matched comparisons."
        ),
        reports=(B3_ROSTER, B3_EVAL, W4_THEORY),
        artifacts=(W4_RUNNER, "agent_skill_loop/memory/retrieval_m35.py"),
        tags=("memory-transfer", "l3-distillation", "attribution"),
    )


def _unified_framework(theory: dict) -> Card:
    framework = theory["unified_4wave_framework"]
    estimand = framework["common_estimand"]
    wave2 = framework["wave_2"]
    waves = (
        ("Wave 1 · Deadline observability", (
            framework["wave_1"]["result"], framework["wave_1"]["hypothesis"],
        )),
        ("Wave 2 · Computational admission and search continuation", (
            wave2["geometry_scale_control"]["model"], *wave2["early_stop_and_restart"]["equations"],
        )),
        ("Wave 3 · Fleet feasibility", (
            framework["wave_3"]["fleet_contract"], *framework["wave_3"]["equations"],
        )),
        ("Wave 4 · Diagnostic evidence and transfer", tuple(framework["wave_4"]["hypotheses"])),
    )
    definitions = [f"- {line}" for line in estimand["equations"]]
    for heading, paragraphs in waves:
        definitions.extend(("", f"### {heading}", "", "\n\n".join(paragraphs)))

    findings = []
    limits = [f"- {line}" for line in estimand["invariants"]]
    for theorem_id, theorem in theory["wave4_theorems"].items():
        findings.extend([
            f"### {theorem_id} · {theorem['title']}",
            "",
            theorem["formal_statement"],
            "",
            *[f"- {equation}" for equation in theorem.get("equations", [])],
            "",
            *[f"- {step}" for step in theorem["proof_sketch"]],
            "",
        ])
        limits.extend(f"- {theorem_id} assumption. {item}" for item in theorem["assumptions"])
    limits.extend([
        "- B2 compares the diagnostic arms at full free-fleet completion. The bound on route-quality "
        "effects additionally depends on the affected objective share and per-instance cost changes.",
        "- B3 estimates neither population variance nor target SNR. The online-versus-offline ordering "
        "is conditional on the stated feedback and selection models.",
    ])
    for example in theory["adversarial_counterexamples"]:
        findings.extend([
            f"### {example['id']}", "", example["construction"], "", example["boundary"], "",
            "```python", example["python_assertions"].rstrip(), "```", "",
        ])

    return Card(
        entry_id="theory-m6-waves1to4-unified-framework-20261127",
        title="M6 Waves 1–4 · Unified deadline, feasibility, and transfer framework",
        summary=framework["thesis"],
        method="\n".join(definitions),
        findings="\n".join(findings),
        limits="\n".join(limits),
        reports=(W1_THEORY, W2_THEORY, W3_THEORY, C1_TIGHTNESS, W4_THEORY),
        artifacts=(W1_RUNNER, W2_RUNNER, W3_RUNNER, W4_RUNNER),
        tags=("deadline-observability", "fleet-feasibility", "signal-to-noise", "counterexamples"),
        entry_type="framework",
        category="optimization_frameworks_experiments",
        paradigm="math_mechanism",
        knowledge_tier="math_observation",
    )


def sync_milestone6_kb(workspace_dir: Path) -> dict[str, Any]:
    report_paths = (
        W1_SUMMARY, W1_THEORY, C2_OFFLINE, B1_EVAL, W2_THEORY, C1_OFFLINE, C1_EVAL, W3_THEORY,
        C1_TIGHTNESS, B2_ATTEMPT1, B2_PILOT, B2_EVAL, B3_ROSTER, B3_EVAL, W4_THEORY,
    )
    reports = {path: read_json(REPO / path) for path in report_paths}
    cards = (
        _wave1(reports[W1_SUMMARY], reports[W1_THEORY]),
        _wave2_c2(reports[C2_OFFLINE], reports[W2_THEORY]),
        _wave2_b1(reports[B1_EVAL], reports[W2_THEORY]),
        _wave3(reports[C1_OFFLINE], reports[C1_EVAL], reports[W3_THEORY], reports[C1_TIGHTNESS]),
        _wave4_b2(reports[B2_ATTEMPT1], reports[B2_PILOT], reports[B2_EVAL], reports[W4_THEORY]),
        _wave4_b3(reports[B3_ROSTER], reports[B3_EVAL]),
        _unified_framework(reports[W4_THEORY]),
    )
    commit = _head_short_commit()
    artifact_paths = dict.fromkeys(path for card in cards for path in card.artifacts)
    pins = {path: _pin(path, commit) for path in artifact_paths}
    _ensure_source(workspace_dir, reports)
    entries_dir = workspace_dir / "entries"
    for card in cards:
        _write_card(entries_dir, card, pins)
    return {"written": [card.entry_id for card in cards], "total_entries": len(list(entries_dir.glob("*.json")))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-id", default=M6_RELEASE_ID)
    args = parser.parse_args(argv)

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.release_id):
        parser.error("invalid release ID")
    store = REPO / "knowledge_store"
    if os.path.lexists(store / "releases" / args.release_id):
        parser.error(f"release already exists and is immutable: {args.release_id}")

    prior = store / "releases" / M5_RELEASE_ID
    directories = ("suites", "routes", "traces", "results", "published_results")
    filenames = ("algorithms.json", "workbench_manifest.json")
    if not prior.is_dir():
        raise FileNotFoundError(f"Prior immutable M5 release missing: {prior}")
    for name in directories:
        if not (prior / name).is_dir():
            raise FileNotFoundError(f"Missing M5 workbench directory: {prior / name}")
    for name in filenames:
        if not (prior / name).is_file():
            raise FileNotFoundError(f"Missing M5 workbench file: {prior / name}")

    workspace = REPO / "knowledge_workspace"
    kb_res = sync_milestone6_kb(workspace)
    ws_val = validate_workspace(workspace)
    if not ws_val["ok"]:
        raise RuntimeError(f"knowledge_workspace_validation_failed:{ws_val['errors'][:10]}")

    build_dir = REPO / "build"
    build_dir.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="m6-release-", dir=build_dir))
    wb_dir = staging / "workbench"
    dash_dir = staging / "dashboard"
    wb_dir.mkdir()
    for name in directories:
        shutil.copytree(prior / name, wb_dir / name)
    for name in filenames:
        shutil.copy2(prior / name, wb_dir / name)

    dash_info = build_dashboard(
        bundle_dir=wb_dir,
        workspace_dir=workspace,
        output_dir=dash_dir,
        release_id=args.release_id,
    )
    rel_info = build_release(
        workspace,
        store,
        args.release_id,
        workbench_bundle=wb_dir,
        dashboard_dir=dash_dir,
        activate=False,
    )
    rel_val = activate_verified_release(store, Path(rel_info["release"]))
    if rel_val.get("pointer") not in {"symlink", "git_symlink_text"}:
        raise RuntimeError(f"knowledge_store/current pointer degraded to {rel_val.get('pointer')!r}")
    rel_info["pointer"] = rel_val["pointer"]
    print(json.dumps({
        "ok": True,
        "kb_sync": kb_res,
        "dashboard": dash_info,
        "release": rel_info,
        "release_validation_ok": rel_val["ok"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
