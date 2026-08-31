"""由 FMEResearchLoop 驱动的在线对照；不调用旧 EOH 进化主循环。"""
from __future__ import annotations

import json
import hashlib
import os
import random
from dataclasses import asdict, replace
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median
from typing import Any

from eoh_rag.experiments.provider import load_local_env
from eoh_rag.experiments.research_contracts import AlgorithmBehaviorProfile, CounterexampleArtifact, EvaluationResult, MechanismClaim
from eoh_rag.fme.archives import FMEArchives, CounterexampleAdmissionEvidence
from eoh_rag.fme.analysis import AnalysisRecord, QuestionStack, ResearchQuestion, structured_analysis_prompt
from eoh_rag.fme.cold_start import ColdStartMode, FrozenEvidenceRetriever, HistoricalEvidenceItem, render_evidence_context
from eoh_rag.fme.controller import FMEAction, FMEController
from eoh_rag.fme.mainline import GenerationRequest, build_fme_mainline
from eoh_rag.fme.online_adapters import (
    ROOT, EOHGeneratorAdapter, EvidenceJournal, FixtureTransport, ChatCompletionTransport,
    ProviderFailure, digest, file_hash, verify_journal,
)
from eoh_rag.fme.pilot_evaluation import SubprocessEvaluator, build_suite, get_problem_spec
from eoh_rag.fme.potential import AnalysisOutcome, QualityObservation, analysis_potential_metrics, quality_potential_curve
from eoh_rag.fme.problem_adapters import CounterexampleValidityPolicy
from eoh_rag.fme.research_loop import FrozenReplayContract, ReplayActionResult, ReplayEvidenceState


class FixedGenerationController(FMEController):
    """标量与被动组仍由同一 loop 调度，只取消主动科学动作。"""

    def choose_action(self, state):
        if state.remaining_evaluation_budget <= 0:
            return self._decision(FMEAction.STOP_BRANCH, 1, 0, "action_credit_exhausted")
        return self._decision(FMEAction.INVENT_ALGORITHM, 1, 1, "preregistered_passive_generation")


def load_protocol(path: Path, *, smoke: bool = False) -> dict[str, Any]:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if "extends" in protocol:
        base_path = ROOT / protocol["extends"]
        base = json.loads(base_path.read_text(encoding="utf-8"))
        if "extends" in base:
            raise ValueError("nested_protocol_extension_not_supported")
        protocol = {**base, **protocol, "base_manifest_hash": file_hash(base_path)}
    if protocol.get("schema_version") != "fme-online-pilot/v2":
        raise ValueError("unsupported_online_protocol")
    for key in ("candidate_attempts", "action_tick_cap", "development_instances_per_suite", "heldout_instances"):
        if not isinstance(protocol[key], int) or protocol[key] < 1:
            raise ValueError(f"invalid_protocol_{key}")
    if set(protocol["problems"]) != {"bp_online", "tsp_construct", "cvrp_construct"}:
        raise ValueError("pilot_requires_three_mainline_problems")
    ids = [arm["id"] for arm in protocol["arms"]]
    if len(ids) != len(set(ids)) or len(protocol["seeds"]) != len(set(protocol["seeds"])):
        raise ValueError("duplicate_protocol_coordinates")
    for arm in protocol["arms"]:
        if arm["controller"] not in {"scalar", "passive", "active"}:
            raise ValueError("invalid_controller_arm")
        ColdStartMode(arm["history"])
        if arm["model_slot"] not in protocol["model_slots"]:
            raise ValueError("unknown_model_slot")
    for pairs in protocol["comparisons"].values():
        if any(left not in ids or right not in ids for left, right in pairs):
            raise ValueError("invalid_contrast")
    normalized_history = (ROOT / protocol["history_snapshot"]).read_bytes().replace(b"\r\n", b"\n")
    if hashlib.sha256(normalized_history).hexdigest() != protocol["history_sha256"]:
        raise ValueError("frozen_history_snapshot_hash_mismatch")
    protocol["source_manifest_hash"] = file_hash(path)
    protocol["source_manifest_path"] = str(path.relative_to(ROOT)).replace("\\", "/")
    protocol["mode"] = "integration_smoke" if smoke else "online"
    if smoke:
        protocol.update(seeds=[20260831], candidate_attempts=3, action_tick_cap=24,
                        development_instances_per_suite=2, heldout_instances=2,
                        sizes={"bp_online": 24, "tsp_construct": 12, "cvrp_construct": 12})
    return protocol


def freeze_protocol(protocol: dict[str, Any]) -> dict[str, Any]:
    load_local_env()
    result = dict(protocol)
    result["history_raw_bytes_sha256"] = file_hash(ROOT / protocol["history_snapshot"])
    result["resolved_models"] = {
        slot: f"integration-fixture/{slot}" if protocol["mode"] == "integration_smoke" else os.environ.get(env, "").strip()
        for slot, env in protocol["model_slots"].items()
    }
    source_files = [
        "eoh_rag/fme/online_pilot.py", "eoh_rag/fme/online_adapters.py", "eoh_rag/fme/pilot_evaluation.py",
        "scripts/fme_pilot_eval_worker.py", "eoh_rag/fme/controller.py", "eoh_rag/fme/research_loop.py",
        "eoh_rag/fme/analysis.py", "eoh_rag/fme/cold_start.py", "eoh_rag/fme/potential.py",
        "eoh_rag/fme/archives.py", "eoh_rag/fme/mainline.py", "eoh_rag/fme/problem_adapters.py",
        "eoh_rag/experiments/research_contracts.py", protocol["history_snapshot"],
        "eoh_rag/experiments/provider.py",
        "official_eoh/eoh/src/eoh/eoh/evolution.py", protocol["abstract_mechanisms"],
        "official_eoh/examples/bp_online/prob.py", "official_eoh/examples/tsp_construct/prob.py",
        "official_eoh/examples/cvrp_construct/prob.py",
    ]
    result["source_hashes"] = {name: file_hash(ROOT / name) for name in source_files}
    result["source_hashes"][protocol["source_manifest_path"]] = protocol["source_manifest_hash"]
    if "extends" in protocol:
        result["source_hashes"][protocol["extends"]] = file_hash(ROOT / protocol["extends"])
    # held-out 只冻结哈希，不传入模型、生成器、科学状态或开发域 worker。
    result["suite_hashes"] = {}
    for problem in protocol["problems"]:
        for seed in protocol["seeds"]:
            for split in ("dev_train", "dev_probe", "heldout"):
                count = protocol["heldout_instances"] if split == "heldout" else protocol["development_instances_per_suite"]
                suite = build_suite(problem, seed, split, count=count, size=protocol["sizes"][problem])
                result["suite_hashes"][f"{problem}/{seed}/{split}"] = suite["content_hash"]
    result["protocol_hash"] = digest(result)
    return result


def preflight(protocol: dict[str, Any], journal: EvidenceJournal) -> dict[str, Any]:
    models = protocol["resolved_models"]
    results: dict[str, Any] = {}
    for slot, model in models.items():
        if not model:
            results[slot] = {"ok": False, "error_code": "model_slot_not_configured"}
            continue
        transport = ChatCompletionTransport(model, journal, temperature=0, generation_tokens=64, analysis_tokens=64,
            timeout=protocol["provider_timeout_seconds"], provider=protocol["provider"], thinking=protocol.get("thinking"))
        try:
            transport.request("Reply only OK.", purpose="preflight", problem="none")
            results[slot] = {"ok": True, "model": model}
        except ProviderFailure as exc:
            results[slot] = {"ok": False, "model": model, "http_status": exc.status, "error_code": exc.error_code}
    distinct = len(set(value for value in models.values() if value)) == len(models)
    receipt = {"ok": all(item["ok"] for item in results.values()) and distinct,
               "models_distinct": distinct, "model_results": results,
               "protocol_hash": protocol["protocol_hash"], "cohort_started": False}
    journal.append("provider_gate", receipt)
    return receipt


def make_retriever(protocol: dict[str, Any], mode: ColdStartMode) -> FrozenEvidenceRetriever:
    for name in (protocol["abstract_mechanisms"], protocol["history_snapshot"]):
        if file_hash(ROOT / name) != protocol["source_hashes"][name]:
            raise ValueError("frozen_retrieval_source_changed")
    if mode in {ColdStartMode.ABSTRACT_TRANSFER, ColdStartMode.SHUFFLED_ABSTRACT_TRANSFER}:
        asset = json.loads((ROOT / protocol["abstract_mechanisms"]).read_text(encoding="utf-8"))
        if asset["visible_scope"] != "dev_only" or asset["status"] != "unconfirmed_target_hypotheses":
            raise ValueError("abstract_transfer_scope_invalid")
        items = [HistoricalEvidenceItem.create(**item, source_kind="mechanism") for item in asset["items"]]
        return FrozenEvidenceRetriever(items, snapshot_id=file_hash(ROOT / protocol["abstract_mechanisms"]))
    return FrozenEvidenceRetriever.from_jsonl(ROOT / protocol["history_snapshot"], snapshot_id=protocol["history_sha256"])


def _parse_analysis(text: str) -> dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[1].rsplit("```", 1)[0]
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("analysis_must_be_json_object")
    return parsed


class PilotCell:
    def __init__(self, protocol: dict[str, Any], arm: dict[str, str], problem: str, seed: int, directory: Path) -> None:
        self.protocol, self.arm, self.problem, self.seed = protocol, arm, problem, seed
        self.fixture = protocol["mode"] == "integration_smoke"
        self.actor = "integration_fixture" if self.fixture else "research_agent"
        self.journal = EvidenceJournal(directory, actor=self.actor)
        self.spec = get_problem_spec(problem)
        self.evaluator = SubprocessEvaluator(timeout=protocol["evaluator_timeout_seconds"])
        self.suites = {split: build_suite(problem, seed, split, count=protocol["development_instances_per_suite"],
                                         size=protocol["sizes"][problem]) for split in ("dev_train", "dev_probe")}
        for split, suite in self.suites.items():
            if suite["content_hash"] != protocol["suite_hashes"][f"{problem}/{seed}/{split}"]:
                raise ValueError("suite_hash_drift")
        model = protocol["resolved_models"][arm["model_slot"]]
        self.transport = FixtureTransport(model, self.journal, self.spec) if self.fixture else ChatCompletionTransport(
            model, self.journal, temperature=protocol["temperature"], generation_tokens=protocol["generation_max_tokens"],
            analysis_tokens=protocol["analysis_max_tokens"], timeout=protocol["provider_timeout_seconds"],
            provider=protocol["provider"], thinking=protocol.get("thinking"))
        self.generator = EOHGeneratorAdapter(self.spec, self.transport)
        self.retriever = make_retriever(protocol, ColdStartMode(arm["history"]))
        composition = build_fme_mainline(generator=self.generator, evidence_retriever=self.retriever)
        self.loop = composition.research_loop
        if arm["controller"] != "active":
            # 同一个类/入口，仅替换预注册 controller policy，不创建第二顶层。
            from eoh_rag.fme.research_loop import FMEResearchLoop
            self.loop = FMEResearchLoop(FixedGenerationController())
        self.problem_adapter = composition.problem_adapters[problem]
        self.attempts = self.failures = self.valid = self.solver_calls = 0
        self.archives = FMEArchives(directory / "archives")
        self.pending_probe = None
        self.repair_attempted_claims: set[str] = set()
        self.counterexample_searches = 0
        self.latest = None
        self.feedback = ""
        self.last_analysis = ""
        self.questions = QuestionStack(problem, (ResearchQuestion("initial", "Which mechanism improves the current baseline on development data, and where does it fail?", 100),))
        self.analysis_outcomes: list[AnalysisOutcome] = []
        self.observations: list[QualityObservation] = []
        self.population: list[dict[str, Any]] = []
        self.initial_objective = 0.0
        self.retrieved_item_ids: tuple[str, ...] = ()

    def archive_algorithm(self, row: dict[str, Any]) -> None:
        train = row["results"]["dev_train"]
        baseline = self.baseline_results["dev_train"]["instance_objectives"]
        gaps = {str(i): (score-base)/max(abs(base), 1e-12)
                for i, (score, base) in enumerate(zip(train["instance_objectives"], baseline))}
        profile = AlgorithmBehaviorProfile.create(candidate_id=row["candidate_id"], problem=self.problem,
            per_distribution_relative_gap={"dev_train": (row["objective"]-self.initial_objective)/self.initial_objective},
            feasibility_rate=1.0, timeout_rate=0.0, runtime_profile_seconds={}, scale_sensitivity=0.0,
            feature_sensitivity=gaps)
        evaluation = EvaluationResult(row["candidate_id"], self.suites["dev_train"]["content_hash"],
            row["objective"], True, None, None, digest(train),
            {"visible_scope": "dev_only", "profile_boundary": "fixed_size_instance_signature_not_measured_scale_sensitivity"})
        admission = self.archives.admit_algorithm(profile, evaluation)
        self.journal.append("algorithm_admission", {"admission": asdict(admission),
            "profile": profile.to_dict(), "evaluation": evaluation.to_dict()})

    def sync_state(self, state: ReplayEvidenceState) -> ReplayEvidenceState:
        snapshot = self.archives.snapshot()
        claims = snapshot["mechanism_claims"]
        archive_hash = self.journal.append("archive_snapshot", snapshot)
        return replace(state, algorithm_archive_size=len(snapshot["algorithms"]),
            counterexample_archive_size=len(snapshot["counterexamples"]),
            proposed_claim_count=sum(c["state"] == "proposed" for c in claims),
            weakened_claim_count=sum(c["state"] == "weakened" and c["claim_id"] not in self.repair_attempted_claims for c in claims),
            supported_claim_count=sum(c["state"] == "supported" for c in claims),
            pending_counterexample_comparisons=int(self.pending_probe is not None),
            recent_generation_attempts=self.attempts, recent_generation_failures=self.failures,
            counterexample_searches_since_generation=self.counterexample_searches,
            remaining_generation_budget=self.protocol["candidate_attempts"]-self.attempts,
            evidence_hashes=tuple(sorted(set(state.evidence_hashes+(archive_hash,)))))

    def evaluate(self, code: str) -> dict[str, Any]:
        result = {}
        for split, suite in self.suites.items():
            self.solver_calls += 1
            result[split] = self.evaluator.evaluate(self.problem, code, suite)
        return result

    def start(self) -> ReplayEvidenceState:
        result = self.evaluate(self.spec["baseline_code"])
        self.journal.append("external_teacher_baseline", result)
        if not all(row["valid"] for row in result.values()):
            raise ValueError("baseline_evaluator_failed")
        self.initial_objective = float(result["dev_train"]["objective"])
        self.baseline_results = result
        code = self.spec["baseline_code"]
        self.population = [{"candidate_id": digest(code), "algorithm": "deterministic external_teacher baseline",
                            "code": code, "objective": self.initial_objective, "results": result, "other_inf": None}]
        self.archive_algorithm(self.population[0])
        return self.sync_state(ReplayEvidenceState(self.protocol["action_tick_cap"], 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                   (self.protocol["protocol_hash"], self.suites["dev_train"]["content_hash"])))

    def generate(self, action: FMEAction) -> ReplayActionResult:
        if self.attempts >= self.protocol["candidate_attempts"]:
            raise ValueError("candidate_budget_exceeded")
        if action is FMEAction.TRANSFER_ABSTRACT_MECHANISM:
            raise ValueError("active_transfer_not_in_depth_first_pilot")
        self.attempts += 1
        self.counterexample_searches = 0
        self.latest = None
        self.pending_probe = None
        self.repair_attempted_claims.update(c["claim_id"] for c in self.archives.snapshot()["mechanism_claims"] if c["state"] == "weakened")
        parent = self.population[0]
        history_mode = ColdStartMode(self.arm["history"])
        transfer_mode = history_mode in {ColdStartMode.ABSTRACT_TRANSFER, ColdStartMode.SHUFFLED_ABSTRACT_TRANSFER}
        evidence = self.retriever.retrieve_for_mode(problem=self.problem, query=self.spec["task_description"],
            limit=self.protocol["abstract_history_limit"] if transfer_mode else self.protocol["history_limit"],
            mode=history_mode, seed=self.seed)
        self.retrieved_item_ids = tuple(item.item_id for item in evidence)
        rendered_evidence = tuple(replace(item, text=item.text[:self.protocol["history_chars_per_item"]]) for item in evidence)
        context = render_evidence_context(rendered_evidence)
        evidence_hashes = (self.suites["dev_train"]["content_hash"], digest(parent["results"]["dev_train"])) + tuple(item.evidence_hash for item in evidence)
        if self.arm["controller"] != "scalar":
            context += "\nPrevious prospective analysis (not a proof):\n" + self.last_analysis
            context += "\n" + self.questions.to_prompt()
        if self.arm["controller"] == "active":
            context += "\nDevelopment falsification feedback:\n" + self.feedback
        retrieval_hash = self.journal.append("retrieval", {"attempt": self.attempts, "mode": self.arm["history"],
            "snapshot_id": self.retriever.snapshot_id, "items": [asdict(item) for item in evidence], "rendered_context_hash": digest(context)})
        self.generator.parents = self.population[:2]
        request = GenerationRequest(self.problem, action.value, tuple(p["candidate_id"] for p in self.generator.parents), evidence_hashes, context)
        claim_admission = None
        claim = None
        try:
            generated = self.generator.generate(request)
            if len(generated) != 1:
                raise ValueError("generation_extraction_failed")
            candidate = generated[0]
            candidate_id = digest(candidate.code)
            code_path = self.journal.save_candidate(candidate_id, candidate.code)
            analysis_prompt = structured_analysis_prompt(problem=self.problem,
                candidate_summary=candidate.algorithm + "\n" + candidate.code,
                evidence_context=json.dumps(parent["results"]["dev_train"], ensure_ascii=False) + "\n" + context,
                question_stack=self.questions)
            analysis_prompt += ("\nPredict relative improvement of THIS candidate versus the provided parent on dev_train "
                "before evaluation: (parent_objective-candidate_objective)/abs(parent_objective). "
                "Probability means strictly positive improvement. next_action must be one of " + ", ".join(a.value for a in FMEAction))
            analysis_raw = self.transport.request(analysis_prompt, purpose="analysis", problem=self.problem)
            fields = _parse_analysis(analysis_raw)
            analysis = AnalysisRecord.create(problem=self.problem, candidate_id=candidate_id,
                parent_candidate_ids=candidate.parent_candidate_ids, evidence_hashes=evidence_hashes,
                prompt_hash=digest(analysis_prompt), question_ids=tuple(q.question_id for q in self.questions.questions),
                actor=self.actor, observation=fields["observation"], mechanism_hypothesis=fields["mechanism_hypothesis"],
                predicted_effect=float(fields["predicted_effect"]), predicted_success_probability=float(fields["predicted_success_probability"]),
                predicted_regime=fields["predicted_regime"], predicted_risk=fields["predicted_risk"],
                cheapest_falsification=fields["cheapest_falsification"], next_action=FMEAction(fields["next_action"]))
            # 先 append+fsync，之后才能调用任何候选评估器。
            analysis_hash = self.journal.append("prospective_analysis", analysis.to_dict())
            claim = MechanismClaim.create(claim_id=analysis.analysis_id, claim=analysis.mechanism_hypothesis,
                source_problem=self.problem, supporting_case_ids=(), counterexample_ids=(),
                linked_candidate_ids=(candidate_id,), linked_diff_hashes=(digest((parent["candidate_id"], candidate_id)),),
                applicability=analysis.predicted_regime, evidence_level="development_only", actor=self.actor,
                cheapest_next_falsification=analysis.cheapest_falsification)
            claim_admission = self.archives.admit_claim(claim)
            self.journal.append("prospective_claim", {"claim": claim.to_dict(), "admission": asdict(claim_admission)})
            self.last_analysis = json.dumps(analysis.to_dict(), ensure_ascii=False)
            result = self.evaluate(candidate.code)
            valid = all(row["valid"] for row in result.values())
            outcome_hash = self.journal.append("candidate_evaluation", {"candidate_id": candidate_id,
                "attempt": self.attempts, "analysis_id": analysis.analysis_id, "analysis_event_hash": analysis_hash,
                "code_path": code_path, "generation_prompt_hash": self.generator.last_prompt_hash,
                "operator": candidate.operator, "results": result, "valid": valid})
            self.latest = {"candidate_id": candidate_id, "algorithm": candidate.algorithm, "code": candidate.code,
                           "results": result, "parent_results": parent["results"], "parent_id": parent["candidate_id"],
                           "claim_id": claim.claim_id if claim_admission.admitted else None, "valid": valid, "analysis": analysis}
            if not valid:
                if claim_admission.admitted:
                    admission = self.archives.transition_claim(claim.claim_id, "weakened", (outcome_hash,), "candidate_invalid_not_mechanism_refutation")
                    self.journal.append("claim_transition", asdict(admission))
                self.failures += 1
                self.feedback = "Candidate invalid on development; restore interface/feasibility before optimizing."
                self.observations.append(QualityObservation(self.attempts, self.population[0]["objective"]))
                return ReplayActionResult(action, "failed", (outcome_hash,), failure_hash=outcome_hash)
            self.valid += 1
            actual = (parent["objective"] - float(result["dev_train"]["objective"])) / max(abs(parent["objective"]), 1e-12)
            self.analysis_outcomes.append(AnalysisOutcome(analysis.analysis_id, analysis.predicted_effect,
                                                        analysis.predicted_success_probability, actual))
            row = {"candidate_id": candidate_id, "algorithm": candidate.algorithm, "code": candidate.code,
                   "objective": float(result["dev_train"]["objective"]), "results": result, "other_inf": None}
            # 重复候选仍占预算，但不伪增算法多样性。
            if candidate_id not in {p["candidate_id"] for p in self.population}:
                self.population.append(row)
                self.archive_algorithm(row)
            self.population.sort(key=lambda p: (p["objective"], p["candidate_id"]))
            question = ResearchQuestion(f"candidate-{self.attempts}", analysis.cheapest_falsification, 100 + self.attempts,
                                        parent_question_id="initial", evidence_hashes=(outcome_hash,))
            self.questions = QuestionStack(self.problem, (self.questions.questions[0], question))
            self.journal.append("question_stack", asdict(self.questions))
            self.observations.append(QualityObservation(self.attempts, self.population[0]["objective"]))
            return ReplayActionResult(action, "completed", (outcome_hash, retrieval_hash), claim_delta=int(claim_admission.admitted))
        except ProviderFailure:
            # Provider 故障是 cohort 终止，不应作为算法质量失败吞掉后继续刷请求。
            raise
        except (ValueError, TypeError, KeyError, AttributeError, SyntaxError) as exc:
            self.failures += 1
            receipt = self.journal.append("candidate_attempt_failure", {"attempt": self.attempts, "error_code": type(exc).__name__})
            if claim is not None and claim_admission is not None and claim_admission.admitted:
                admission = self.archives.transition_claim(claim.claim_id, "weakened", (receipt,), "attempt_failed_after_prospective_claim")
                self.journal.append("claim_transition", asdict(admission))
            self.feedback = "Generation or structured analysis contract failed; simplify and satisfy the exact interface."
            self.observations.append(QualityObservation(self.attempts, self.population[0]["objective"]))
            return ReplayActionResult(action, "failed", (receipt,), failure_hash=receipt)

    def choose_counterexample(self, state: ReplayEvidenceState) -> ReplayActionResult:
        # 只在冻结开发实例中选择反例候选；选择/拒绝本身也保留，绝不假装新发现分布。
        self.counterexample_searches += 1
        if len(self.population) < 2:
            receipt = self.journal.append("counterexample_selection", {"status": "no_valid_comparison"})
            return ReplayActionResult(FMEAction.GENERATE_COUNTEREXAMPLE, "completed", (receipt,))
        strong, comparator = self.population[:2]
        scores = strong["results"]["dev_train"]["instance_objectives"]
        other_scores = comparator["results"]["dev_train"]["instance_objectives"]
        index = max(range(len(scores)), key=lambda i: scores[i] - other_scores[i])
        instance = self.suites["dev_train"]["instances"][index]
        validity = self.problem_adapter.validate_challenge(instance, self.challenge_policy(instance))
        delta = scores[index] - other_scores[index]
        artifact = CounterexampleArtifact(digest((self.problem, self.seed, index)), self.problem,
            "frozen_dev_train", f"{self.problem}/frozen_dev_train", digest(instance),
            f"{self.suites['dev_train']['content_hash']}#{index}", "select_existing_development_instance", self.actor)
        ranking = tuple(p["candidate_id"] for p in sorted((strong, comparator),
            key=lambda p: (p["results"]["dev_train"]["instance_objectives"][index], p["candidate_id"])))
        admission = None
        if validity.domain_validity_status == "valid":
            admission = self.archives.admit_counterexample(artifact, CounterexampleAdmissionEvidence(
                (strong["candidate_id"], comparator["candidate_id"]),
                (strong["candidate_id"],) if delta > 1e-12 else (), (strong["candidate_id"],), ranking))
        admitted = admission is not None and admission.admitted
        if admitted:
            self.pending_probe = {"index": index, "counterexample_id": artifact.counterexample_id,
                "strong_id": strong["candidate_id"], "comparator_id": comparator["candidate_id"]}
        receipt = self.journal.append("counterexample_selection", {"index": index, "artifact": artifact.to_dict(),
            "strong_candidate_id": strong["candidate_id"], "comparator_id": comparator["candidate_id"],
            "validity": asdict(validity), "regression": delta, "admitted": admitted,
            "admission": asdict(admission) if admission else None,
            "boundary": "selected_from_frozen_development_suite_not_new_distribution"})
        return ReplayActionResult(FMEAction.GENERATE_COUNTEREXAMPLE, "completed", (receipt,), counterexample_delta=int(admitted))

    def challenge_policy(self, artifact: dict[str, Any]) -> CounterexampleValidityPolicy:
        # 名义签名是预注册生成分布的几何中心/比例，不从本次反例倒推匹配签名。
        if self.problem == "bp_online":
            signature, distance = (0.25, 0.25, 0.25, 0.25), 0.75
        elif self.problem == "tsp_construct":
            signature, distance = (0.5, 0.5, 0.2), 1.5
        else:
            signature, distance = (0.5, 0.5, 0.15), 1.5
        size = self.protocol["sizes"][self.problem]
        return CounterexampleValidityPolicy(self.problem, distance, size, size, signature)

    def compare(self, state: ReplayEvidenceState) -> ReplayActionResult:
        probe = self.pending_probe
        if probe is None:
            raise ValueError("counterexample_comparison_not_bound")
        rows = {p["candidate_id"]: p for p in self.population}
        index = probe["index"]
        delta = rows[probe["strong_id"]]["results"]["dev_train"]["instance_objectives"][index] - rows[probe["comparator_id"]]["results"]["dev_train"]["instance_objectives"][index]
        payload = {**probe, "scope": "dev_only", "regret": delta,
                   "status": "strong_candidate_degraded_on_selected_case" if delta > 1e-12 else "not_degraded"}
        self.pending_probe = None
        self.feedback = json.dumps(payload)
        receipt = self.journal.append("counterexample_comparison", payload)
        return ReplayActionResult(FMEAction.COMPARE_ON_COUNTEREXAMPLE, "completed", (receipt,))

    def retest(self, state: ReplayEvidenceState) -> ReplayActionResult:
        latest = self.latest
        if not latest or not latest["valid"] or not latest["claim_id"]:
            raise ValueError("claim_retest_not_bound")
        parent = latest["parent_results"]["dev_probe"]["objective"]
        candidate = latest["results"]["dev_probe"]["objective"]
        gain = (parent - candidate) / max(abs(parent), 1e-12)
        prediction = latest["analysis"].predicted_effect
        supported = gain > 1e-12 and prediction > 0
        payload = {"candidate_id": latest["candidate_id"], "claim_id": latest["claim_id"],
            "relative_gain": gain, "scope": "independent_dev_probe_not_heldout",
            "status": "development_direction_consistent" if supported else "insufficient_improvement_support",
            "boundary": "direction_check_not_causal_mechanism_validation"}
        self.feedback += "\n" + json.dumps(payload)
        receipt = self.journal.append("claim_retest", payload)
        admission = self.archives.transition_claim(latest["claim_id"], "supported" if supported else "weakened",
            (receipt,), payload["status"])
        if not admission.admitted:
            raise ValueError("claim_transition_rejected")
        transition = self.journal.append("claim_transition", asdict(admission))
        return ReplayActionResult(FMEAction.RETEST_OR_REFUTE_CLAIM, "completed", (receipt, transition), claim_delta=-1)

    def run(self) -> dict[str, Any]:
        state = self.start()
        contract = FrozenReplayContract(self.protocol["study_id"], self.protocol["protocol_hash"], tuple(FMEAction), actor=self.actor)
        adapters = {
            FMEAction.INVENT_ALGORITHM: lambda s: self.generate(FMEAction.INVENT_ALGORITHM),
            FMEAction.REPAIR_FAILED_MECHANISM: lambda s: self.generate(FMEAction.REPAIR_FAILED_MECHANISM),
            FMEAction.TRANSFER_ABSTRACT_MECHANISM: lambda s: self.generate(FMEAction.TRANSFER_ABSTRACT_MECHANISM),
            FMEAction.GENERATE_COUNTEREXAMPLE: self.choose_counterexample,
            FMEAction.COMPARE_ON_COUNTEREXAMPLE: self.compare,
            FMEAction.RETEST_OR_REFUTE_CLAIM: self.retest,
        }
        def traced(action, adapter):
            def invoke(action_state):
                self.journal.append("action_started", {"action": action.value, "state_hash": digest(asdict(action_state)), "attempts_before": self.attempts})
                try:
                    result = adapter(action_state)
                except Exception as exc:
                    self.journal.append("action_aborted", {"action": action.value, "error_code": type(exc).__name__})
                    raise
                self.journal.append("action_finished", asdict(result))
                return result
            return invoke
        adapters = {action: traced(action, adapter) for action, adapter in adapters.items()}
        stop_reason = "candidate_budget_exhausted"
        while self.attempts < self.protocol["candidate_attempts"] or (self.arm["controller"] == "active" and (state.pending_counterexample_comparisons or state.proposed_claim_count)):
            outcome = self.loop.run(contract, state, adapters)
            self.journal.append("scientific_tick", asdict(outcome.decision_record))
            if outcome.stop_record:
                stop_reason = outcome.stop_record.reason
                self.journal.append("stop", asdict(outcome.stop_record))
                break
            state = self.sync_state(outcome.next_state)
            self.journal.append("state_sync", asdict(state))
        incumbent = self.population[0]
        incumbent_path = self.journal.save_candidate(incumbent["candidate_id"], incumbent["code"])
        curve = quality_potential_curve(initial_objective=self.initial_objective, observations=self.observations,
                                        maximum_budget=self.protocol["candidate_attempts"], integration="step") if self.observations else None
        result = {"cell_id": f"{self.problem}/{self.seed}/{self.arm['id']}", "problem": self.problem,
            "seed": self.seed, "arm": self.arm, "actor": self.actor, "model": self.transport.model,
            "status": "completed" if self.attempts == self.protocol["candidate_attempts"] else "incomplete",
            "stop_reason": stop_reason, "candidate_attempts": self.attempts, "valid_candidates": self.valid,
            "failed_attempts": self.failures, "development_solver_calls": self.solver_calls,
            "request_count": len(self.transport.usage), "usage": self.transport.usage,
            "quality_curve": asdict(curve) if curve else None,
            "analysis_metrics": analysis_potential_metrics(self.analysis_outcomes) if self.analysis_outcomes else None,
            "analysis_metric_boundary": "conditional_on_valid_analyses_and_valid_evaluations_failures_reported_separately",
            "archives": self.archives.snapshot(),
            "retrieved_item_ids": self.retrieved_item_ids,
            "incumbent_id": incumbent["candidate_id"], "incumbent_relative_path": incumbent_path,
            "initial_objective": self.initial_objective, "final_objective": incumbent["objective"],
            "scientific_claim_allowed": False, "protocol_hash": self.protocol["protocol_hash"]}
        self.journal.append("cell_frozen", result)
        result["journal_integrity"] = verify_journal(self.journal.path)
        return result


def summarize_contrasts(protocol: dict[str, Any], cells: list[dict[str, Any]]) -> dict[str, Any]:
    if protocol["mode"] == "integration_smoke":
        return {rq: {"status": "integration_only_not_scientific_evidence"} for rq in protocol["comparisons"]}
    by_key = {(cell["problem"], cell["seed"], cell["arm"]["id"]): cell for cell in cells}
    def eligible(cell):
        return bool(cell and cell["status"] == "completed" and cell.get("heldout_valid")
                    and cell.get("scientific_claim_allowed") and cell.get("quality_curve"))
    output: dict[str, Any] = {}
    for rq, pairs in protocol["comparisons"].items():
        comparisons = []
        for left, right in pairs:
            for problem in protocol["problems"]:
                values, missing = [], []
                for seed in protocol["seeds"]:
                    a, b = by_key.get((problem, seed, left)), by_key.get((problem, seed, right))
                    if not eligible(a) or not eligible(b):
                        missing.append(seed)
                        continue
                    heldout_a, heldout_b = a["heldout"]["incumbent"]["objective"], b["heldout"]["incumbent"]["objective"]
                    same_context = (set(a["retrieved_item_ids"]) == set(b["retrieved_item_ids"]))
                    values.append({"seed": seed, "quality_auc_delta": b["quality_curve"]["auc"] - a["quality_curve"]["auc"],
                        "dev_relative_gain": (a["final_objective"] - b["final_objective"]) / max(abs(a["final_objective"]), 1e-12),
                        "heldout_relative_gain": (heldout_a-heldout_b)/max(abs(heldout_a), 1e-12),
                        "retrieval_item_sets_identical": same_context,
                        "retrieval_discriminating_pair": not same_context if "shuffled" in left else None})
                comparisons.append({"problem": problem, "control": left, "treatment": right, "pairs": values,
                    "missing_seeds": missing, "effect_claim_allowed": not missing and len(values) == len(protocol["seeds"])
                        and ("shuffled" not in left or any(not row["retrieval_item_sets_identical"] for row in values)),
                    "median_heldout_gain": median(row["heldout_relative_gain"] for row in values) if values and not missing else None,
                    "median_dev_gain": median(row["dev_relative_gain"] for row in values) if values and not missing else None})
        output[rq] = {"status": "paired_exploratory_pilot", "contrasts": comparisons}
    # RQ4 另报同问题、同seed的 difference-in-differences，不能从两条模型主效应猜交互。
    interactions = []
    for problem in protocol["problems"]:
        for seed in protocol["seeds"]:
            group = [by_key.get((problem, seed, arm)) for arm in ("scalar", "active", "reference_scalar", "reference_active")]
            if all(eligible(cell) for cell in group):
                a, b, c, d = [cell["quality_curve"]["auc"] for cell in group]
                ha, hb, hc, hd = [cell["heldout"]["incumbent"]["objective"] for cell in group]
                interactions.append({"problem": problem, "seed": seed, "controller_by_model_auc_interaction": (d-c)-(b-a),
                    "heldout_relative_gain_interaction": (hc-hd)/max(abs(hc), 1e-12)-(ha-hb)/max(abs(ha), 1e-12)})
    output["RQ4"]["interactions"] = interactions
    return output


def run_study(protocol: dict[str, Any], directory: Path, *, gate_only: bool = False) -> dict[str, Any]:
    fixture = protocol["mode"] == "integration_smoke"
    journal = EvidenceJournal(directory, actor="integration_fixture" if fixture else "research_agent")
    journal.append("protocol_frozen", protocol)
    (directory / "protocol_frozen.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2), encoding="utf-8")
    if not fixture:
        gate = preflight(protocol, journal)
        if not gate["ok"] or gate_only:
            result = {"status": "preflight_ready" if gate["ok"] else "blocked_before_cohort", "gate": gate, "cells": [], "scientific_claim_allowed": False}
            (directory / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return result
    cells: list[dict[str, Any]] = []
    coordinates = [(problem, seed, arm) for problem in protocol["problems"] for seed in protocol["seeds"] for arm in protocol["arms"]]
    random.Random(20260831).shuffle(coordinates)
    runtime: dict[str, PilotCell] = {}
    terminal_error = None
    def execute_cell(coordinate):
        problem, seed, arm = coordinate
        path = directory / "cells" / problem / str(seed) / arm["id"]
        try:
            cell = PilotCell(protocol, arm, problem, seed, path)
            return cell, cell.run(), None
        except (ProviderFailure, ValueError) as exc:
            error = {"cell_id": f"{problem}/{seed}/{arm['id']}", "error_code": exc.error_code if isinstance(exc, ProviderFailure) else type(exc).__name__}
            return None, None, error
    workers = max(1, min(int(protocol.get("cell_concurrency", 1)), 6))
    # 每个坐标都有独立 loop/账本；固定波次并行，只由主线程写 cohort 日志。
    # 波内出现供应商故障时等已启动坐标结束，不启动下一波，不替换失败坐标。
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for offset in range(0, len(coordinates), workers):
            batch = coordinates[offset:offset+workers]
            for cell, result, error in executor.map(execute_cell, batch):
                if error:
                    terminal_error = terminal_error or error
                    journal.append("cohort_interrupted", error)
                else:
                    runtime[result["cell_id"]] = cell
                    cells.append(result)
                    journal.append("cell_completed", {"cell_id": result["cell_id"], "result_hash": digest(result)})
                    print(json.dumps({"event": "cell_completed", "cell_id": result["cell_id"],
                        "completed": len(cells), "expected": len(coordinates), "valid": result["valid_candidates"],
                        "attempts": result["candidate_attempts"]}), flush=True)
            if terminal_error:
                break
    all_frozen = terminal_error is None and len(cells) == len(coordinates) and all(c["status"] == "completed" for c in cells)
    if all_frozen:
        journal.append("all_incumbents_frozen", {cell["cell_id"]: cell["incumbent_id"] for cell in cells})
        # held-out 只在所有组均冻结后触达；不再生成或修改任何候选/假设。
        for result in cells:
            cell = runtime[result["cell_id"]]
            suite = build_suite(cell.problem, cell.seed, "heldout", count=protocol["heldout_instances"], size=protocol["sizes"][cell.problem])
            if suite["content_hash"] != protocol["suite_hashes"][f"{cell.problem}/{cell.seed}/heldout"]:
                raise ValueError("heldout_suite_hash_drift")
            result["heldout"] = {"incumbent": cell.evaluator.evaluate(cell.problem, cell.population[0]["code"], suite),
                                 "baseline": cell.evaluator.evaluate(cell.problem, cell.spec["baseline_code"], suite)}
            result["heldout_valid"] = all(row["valid"] for row in result["heldout"].values())
            journal.append("heldout_evaluation", {"cell_id": result["cell_id"], "results": result["heldout"]})
    source_integrity = {name: file_hash(ROOT / name) == expected for name, expected in protocol["source_hashes"].items()}
    verified = all_frozen and all(cell.get("heldout_valid") for cell in cells) and all(source_integrity.values())
    for cell in cells:
        cell["scientific_claim_allowed"] = verified and not fixture
    status = "integration_smoke_completed" if verified and fixture else "pilot_completed" if verified else "incomplete"
    summary = {"status": status, "mode": protocol["mode"], "protocol_hash": protocol["protocol_hash"],
        "expected_cells": len(coordinates), "completed_cells": len(cells), "terminal_error": terminal_error,
        "scientific_claim_allowed": verified and not fixture, "heldout_unsealed_after_all_cells_frozen": all_frozen,
        "source_integrity": source_integrity, "all_heldout_valid": all_frozen and all(cell.get("heldout_valid") for cell in cells),
        "cells": cells, "rq_results": summarize_contrasts(protocol, cells)}
    journal.append("study_terminal", {"status": status, "summary_hash": digest(summary)})
    summary["journal_integrity"] = verify_journal(journal.path)
    (directory / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return summary
