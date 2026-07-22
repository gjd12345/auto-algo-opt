# Copyright (c) 2026 Fei Liu. MIT License.
# Project: https://github.com/FeiLiu36/EoH
# Citation: Fei Liu, Xialiang Tong, Mingxuan Yuan, Xi Lin, Fu Luo, Zhenkun Wang, Zhichao Lu,
#           Qingfu Zhang, Evolution of Heuristics: Towards Efficient Automatic Algorithm Design
#           Using Large Language Model, Forty-first International Conference on Machine Learning
#           (ICML), 2024.

import heapq
import hashlib
import json
import os
import time
import random
import logging
import threading
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed

from .evolution import Evolution, _eval_with_timeout, _normalize_evaluation_result
from ._adaptive import _should_stop
from ..utils.logger import setup_logger

logger = logging.getLogger('eoh')


def _normalize_fitness(fitness):
    """Round a raw fitness and discard non-finite values. Returns float or None."""
    return _normalize_evaluation_result(fitness)[0]


def population_management(pop, size):
    pop = [ind for ind in pop if ind['objective'] is not None]
    if not pop:
        return pop
    seen = set()
    unique = []
    for ind in pop:
        if ind['objective'] not in seen:
            seen.add(ind['objective'])
            unique.append(ind)
    return heapq.nsmallest(min(size, len(unique)), unique, key=lambda x: x['objective'])


def behavior_population_management(pop, size):
    """FME 按行为画像保留每格精英，再按开发目标裁剪到固定种群规模。"""
    valid = [ind for ind in pop if ind['objective'] is not None]
    cells = {}
    for individual in valid:
        feedback = individual.get("other_inf") or {}
        profile_hash = feedback.get("behavior_profile_hash")
        # 缺少画像时按代码隔离，避免把多个未知行为误合并为同一格。
        code_hash = hashlib.sha256(
            str(individual.get("code", "")).encode("utf-8")
        ).hexdigest()
        cell_key = profile_hash or f"missing:{code_hash}"
        previous = cells.get(cell_key)
        if previous is None or individual["objective"] < previous["objective"]:
            cells[cell_key] = individual
    return heapq.nsmallest(
        min(size, len(cells)), cells.values(), key=lambda item: item["objective"]
    )


def confirmation_gate(offspring, parents):
    """候选必须同时改善搜索父代且不损害独立开发确认批。"""
    parent_list = parents if isinstance(parents, list) else [parents]
    parent_list = [parent for parent in parent_list if isinstance(parent, dict)]
    if not parent_list:
        return False, {"reason": "missing_parent_feedback"}
    reference = min(parent_list, key=lambda item: float(item["objective"]))
    candidate_feedback = offspring.get("other_inf") or {}
    reference_feedback = reference.get("other_inf") or {}
    candidate_confirm = candidate_feedback.get("confirm_objective")
    reference_confirm = reference_feedback.get("confirm_objective")
    if candidate_confirm is None or reference_confirm is None:
        return False, {"reason": "missing_confirmation_objective"}
    search_improved = float(offspring["objective"]) < float(reference["objective"])
    confirm_not_worse = float(candidate_confirm) <= float(reference_confirm)
    details = {
        "reason": "accepted" if search_improved and confirm_not_worse else "dominance_failed",
        "search_improved": search_improved,
        "confirm_not_worse": confirm_not_worse,
        "reference_search_objective": reference["objective"],
        "candidate_confirm_objective": candidate_confirm,
        "reference_confirm_objective": reference_confirm,
    }
    return search_improved and confirm_not_worse, details


class EOH:
    """Main EoH evolutionary loop."""

    def __init__(self, config, problem):
        self.operators = config.operators
        self.operator_weights = config.operator_weights
        self.pop_size = config.pop_size
        self.n_pop = config.n_pop
        self.output_path = config.output_dir
        self.config = config
        self.problem = problem

        # Async pipeline concurrency (decoupled from pop_size).
        self.num_samplers = max(1, int(config.num_samplers))
        self.num_evaluators = max(1, int(config.num_evaluators))
        self.max_sample_nums = config.max_sample_nums

        self._sample_count = 0
        self._best_obj = None
        self._samples_buffer = []
        self._samples_flushed = 0

        # Guards shared state mutated by sampler threads: the population,
        # sample counters, the buffer flushed to disk, and checkpoint cadence.
        self._lock = threading.Lock()
        self._eval_executor = None
        self._evo_reserved = 0      # evolution-sample slots claimed (budget gate)
        self._evo_registered = 0    # evolution samples completed (checkpoint cadence)
        self._gen_offset = 0        # generation index offset for resumed runs
        # 自适应早停状态(opt-in;默认关闭时下列逻辑不生效)
        self._adaptive_stop = bool(getattr(config, "adaptive_stop", False))
        self._stop_window = max(1, int(getattr(config, "stop_window", 5)))
        self._stop_min_gap = float(getattr(config, "stop_min_gap", 0.0))
        self._gen_best_hist = []    # 逐代 checkpoint 处的 best-so-far 目标值
        self._stop = False          # 自适应早停触发后置 True，worker 提前返回
        self._fme_stalled_ticks = 0
        self._fme_controller = None
        self._fme_recorder = None
        if config.feedback_policy == "fme_aware":
            # FME 是外层科研控制模块；这里仅通过生成缝适配既有 EOH 五算子。
            from eoh_rag.fme.controller import FMEController
            from eoh_rag.fme.recorder import FMEPilotEvidenceRecorder
            self._fme_controller = FMEController()
            self._fme_recorder = FMEPilotEvidenceRecorder(
                os.path.join(self.output_path, "results", "fme_evidence")
            )

        # Spawn-based subprocess evaluation is set up once in the main thread so
        # the per-call guard in _eval_with_timeout never races across threads.
        try:
            if multiprocessing.get_start_method(allow_none=True) != 'spawn':
                multiprocessing.set_start_method('spawn', force=True)
        except RuntimeError:
            pass

        log_path = os.path.join(config.output_dir, "results", "run_log.txt")
        self._logger = setup_logger(log_path, config.debug)

        # 随机源由外层 RunSpec 初始化，避免所有正式 run 被静默固定为同一 seed。
        self.evolution = Evolution(config, problem)

    # ── header ────────────────────────────────────────────────────────────────

    def _log_header(self, cfg):
        ops = " ".join(self.operators)
        llm = cfg.llm
        init_n = 2 * self.pop_size
        budget = self.max_sample_nums if self.max_sample_nums is not None else self.n_pop * self.pop_size
        for line in [
            "=" * 54,
            "  EoH",
            f"  LLM      : {llm.model} @ {llm.api_endpoint}",
            f"  EC       : gen={self.n_pop}  pop={self.pop_size}  ops=[{ops}]",
            f"  Sampling : init={init_n} (2×pop)  evo_budget={budget}",
            f"  Pipeline : samplers={self.num_samplers}  evaluators={self.num_evaluators} (async)",
            f"  Timeout  : llm={llm.timeout}s  eval={self.problem.timeout}s",
            "=" * 54,
        ]:
            self._logger.info(line)

    # ── per-sample record ─────────────────────────────────────────────────────

    _SAMPLE_BATCH = 200

    def _record(self, op: str, offspring) -> bool:
        """Log one sample line, write to sample files. Returns True if new best."""
        self._sample_count += 1

        if offspring is None:
            score_str = "None (generation failed)"
            obj = None
        elif offspring.get('objective') is None:
            score_str = "None (evaluation failed)"
            obj = None
        else:
            obj = offspring['objective']
            score_str = str(obj)

        selection_accepted = bool(offspring.get("selection_accepted", True)) if offspring else False
        if obj is not None and not selection_accepted:
            score_str += " (confirm rejected)"

        is_new_best = (
            obj is not None
            and selection_accepted
            and (self._best_obj is None or obj < self._best_obj)
        )
        if is_new_best:
            self._best_obj = obj

        best_str = str(self._best_obj) if self._best_obj is not None else "N/A"
        marker = "  *" if is_new_best else ""
        self._logger.info(f"  #{self._sample_count:<4} [{op}]  {score_str:<16}  best={best_str}{marker}")

        self._write_sample(op, offspring, is_new_best)
        return is_new_best

    def _write_sample(self, op: str, offspring, is_new_best: bool):
        record = {
            'sample_order': self._sample_count,
            'operator': op,
            'algorithm': offspring.get('algorithm') if offspring else None,
            'code': offspring.get('code') if offspring else None,
            'objective': offspring.get('objective') if offspring else None,
            'selection_accepted': offspring.get('selection_accepted', True) if offspring else False,
            'selection_reason': offspring.get('selection_reason') if offspring else None,
        }
        self._samples_buffer.append(record)
        if len(self._samples_buffer) >= self._SAMPLE_BATCH:
            self._flush_samples()
        if is_new_best:
            path = os.path.join(self.output_path, "results", "samples", "samples_best.json")
            try:
                with open(path, 'w') as f:
                    json.dump(record, f, indent=4)
            except OSError as e:
                self._logger.warning("Could not write best sample to %s: %s", path, e)

    def _flush_samples(self):
        if not self._samples_buffer:
            return
        lo = self._samples_flushed + 1
        hi = self._samples_flushed + len(self._samples_buffer)
        path = os.path.join(self.output_path, "results", "samples", f"samples_{lo}~{hi}.json")
        try:
            with open(path, 'w') as f:
                json.dump(self._samples_buffer, f, indent=4)
            self._samples_flushed += len(self._samples_buffer)
            self._samples_buffer = []
        except OSError as e:
            self._logger.warning("Could not flush samples to %s: %s", path, e)

    # ── main run ──────────────────────────────────────────────────────────────

    def run(self):
        self._log_header(self.config)
        t0 = time.time()

        # One shared evaluation pool feeds both initialisation and evolution.
        # Each task runs in an isolated hard-timeout subprocess, so the pool
        # bounds the number of concurrent evaluation processes to num_evaluators.
        self._eval_executor = ThreadPoolExecutor(
            max_workers=self.num_evaluators, thread_name_prefix="eoh-eval"
        )
        try:
            population, n_start = self._init_population(t0)
            population = self._run_evolution(population, n_start, t0)
        finally:
            self._eval_executor.shutdown(wait=True)
            self._flush_samples()

        elapsed = (time.time() - t0) / 60
        best = population[0]['objective'] if population else 'N/A'
        self._logger.info(f"{'='*54}")
        self._logger.info(f"  Evolution finished.  best={best}  samples={self._sample_count}  time={elapsed:.1f}m")
        self._logger.info(f"{'='*54}\n")

    # ── async pipeline ─────────────────────────────────────────────────────────

    def _build_offspring(
        self, population_snapshot, operator, fme_action_decision=None
    ):
        """Producer step: LLM-generate code, then evaluate it on the eval pool.

        Runs on a sampler thread. The LLM call (I/O) happens inline here; the
        evaluation is submitted to the shared evaluation pool and awaited. A
        single sampler does its generation and evaluation in series, but with
        num_samplers threads the LLM calls of some samplers overlap the
        evaluations of others, so up to num_samplers generations are in flight
        while up to num_evaluators eval subprocesses run concurrently. Set
        num_samplers >= num_evaluators to keep the evaluation pool busy.
        Returns an offspring dict (objective may be None), or None on failure.
        """
        try:
            parents, code, algorithm = self.evolution.generate_code(population_snapshot, operator)
        except Exception as e:
            logger.debug("  [offspring] %s: %s", type(e).__name__, e)
            return None
        if code is None:
            return None

        evaluation_started = time.time()
        try:
            fitness = self._eval_executor.submit(
                _eval_with_timeout, self.problem, code, self.problem.timeout
            ).result()
        except Exception as e:
            logger.debug("  [eval] submit failed: %s: %s", type(e).__name__, e)
            fitness = None
        evaluation_runtime_seconds = time.time() - evaluation_started

        objective, feedback = _normalize_evaluation_result(fitness)
        offspring = {
            'algorithm': algorithm,
            'code': code,
            'objective': objective,
            'other_inf': feedback,
        }
        if self.config.feedback_policy == "fme_aware" and objective is not None:
            if not isinstance(offspring["other_inf"], dict):
                offspring["other_inf"] = {}
            parent_list = parents if isinstance(parents, list) else [parents]
            parent_list = [item for item in parent_list if isinstance(item, dict)]
            claim_state = "proposed"
            if parent_list:
                reference = min(parent_list, key=lambda item: float(item["objective"]))
                candidate_worst = offspring["other_inf"].get("worst_gap_pct")
                reference_worst = (reference.get("other_inf") or {}).get("worst_gap_pct")
                objective_improved = objective < float(reference["objective"])
                worst_not_worse = (
                    candidate_worst is not None
                    and reference_worst is not None
                    and float(candidate_worst) <= float(reference_worst)
                )
                if objective_improved and worst_not_worse:
                    claim_state = "supported"
                elif not objective_improved and not worst_not_worse:
                    claim_state = "weakened"
            offspring["other_inf"]["mechanism_claim"] = algorithm
            offspring["other_inf"]["mechanism_claim_state"] = claim_state
            parent_candidate_ids = tuple(
                hashlib.sha256(str(item.get("code", "")).encode("utf-8")).hexdigest()
                for item in parent_list
                if item.get("code")
            )
            action_decision = fme_action_decision or {
                "action": "invent_algorithm",
                "reason": "initial_generation",
                "score": 1.0,
                "allowed_eoh_operators": ["i1"],
                "selected_operator": operator,
            }
            evidence_summary = self._fme_recorder.record_candidate(
                code=code,
                algorithm=algorithm,
                objective=objective,
                evaluation_runtime_seconds=evaluation_runtime_seconds,
                feedback=offspring["other_inf"],
                parent_candidate_ids=parent_candidate_ids,
                operator=operator,
                action_decision=action_decision,
            )
            offspring["other_inf"]["fme_evidence"] = evidence_summary
        if self.config.feedback_policy in {
            "confirmation_aware",
            "confirmation_gate_only",
        } and objective is not None:
            accepted, gate_details = confirmation_gate(offspring, parents)
            offspring["selection_accepted"] = accepted
            offspring["selection_reason"] = gate_details["reason"]
            if not isinstance(offspring["other_inf"], dict):
                offspring["other_inf"] = {}
            offspring["other_inf"]["selection_gate"] = gate_details
        return offspring

    def _select_operator(self, population):
        if self._fme_controller is None:
            operator = random.choices(
                self.operators, weights=self.operator_weights, k=1
            )[0]
            return operator, None

        from eoh_rag.fme.controller import FMEControllerState

        feedback_rows = [
            item.get("other_inf") or {}
            for item in population
            if isinstance(item, dict)
        ]
        behavior_profiles = {
            row.get("behavior_profile_hash")
            for row in feedback_rows
            if row.get("behavior_profile_hash")
        }
        counterexample_ids = {
            counterexample_id
            for row in feedback_rows
            for counterexample_id in row.get("distinguishing_counterexample_ids", [])
        }
        claim_states = [row.get("mechanism_claim_state") for row in feedback_rows]
        remaining_budget = max(
            0,
            int(self.max_sample_nums or self.n_pop * self.pop_size)
            - self._evo_reserved
            + 1,
        )
        decision = self._fme_controller.choose_generation_action(
            FMEControllerState(
                remaining_evaluation_budget=remaining_budget,
                algorithm_archive_size=len(behavior_profiles),
                counterexample_archive_size=len(counterexample_ids),
                proposed_claim_count=claim_states.count("proposed"),
                weakened_claim_count=claim_states.count("weakened"),
                supported_claim_count=claim_states.count("supported"),
                pending_counterexample_comparisons=0,
                transferable_claim_count=claim_states.count("supported"),
                stalled_ticks=self._fme_stalled_ticks,
            )
        )
        allowed = [
            operator
            for operator in decision.allowed_eoh_operators
            if operator in self.operators
        ]
        if not allowed:
            allowed = list(self.operators)
        operator = random.choice(allowed)
        return operator, {
            "action": decision.action.value,
            "reason": decision.reason,
            "score": decision.score,
            "allowed_eoh_operators": list(decision.allowed_eoh_operators),
            "selected_operator": operator,
        }

    def _sampler_worker(self, population_ref, target, t0):
        """Steady-state evolution loop run by each sampler thread.

        Claims a sample slot under the lock, snapshots the current population,
        generates+evaluates an offspring outside the lock, then registers the
        result. Continues until the shared sample budget is exhausted.
        population_ref is a single-element list holding the live population so
        all threads share the same (mutating, lock-protected) reference.
        """
        while True:
            with self._lock:
                if self._evo_reserved >= target or self._stop:
                    return
                self._evo_reserved += 1
                snapshot = list(population_ref[0])

            # Every reserved slot must reach exactly one registration below, or
            # the budget could never complete (the slot is already counted).
            # Nothing here is allowed to escape and kill the worker thread —
            # a dead worker would silently under-produce and possibly hang the
            # run. So the whole body is defensively guarded.
            off = None
            try:
                op, fme_decision = self._select_operator(snapshot)
                off = self._build_offspring(snapshot, op, fme_decision)
                if off is not None and fme_decision is not None:
                    if not isinstance(off.get("other_inf"), dict):
                        off["other_inf"] = {}
                    off["other_inf"]["fme_action_decision"] = fme_decision
            except Exception as e:
                logger.warning("  [sampler] generation error: %s: %s", type(e).__name__, e)
                op = "?"

            with self._lock:
                try:
                    improved = self._record(op, off)
                    if self._fme_controller is not None:
                        self._fme_stalled_ticks = 0 if improved else self._fme_stalled_ticks + 1
                    if (
                        off
                        and off['objective'] is not None
                        and off.get("selection_accepted", True)
                    ):
                        population_ref[0].append(off)
                        manager = (
                            behavior_population_management
                            if self._fme_controller is not None
                            else population_management
                        )
                        population_ref[0] = manager(population_ref[0], self.pop_size)
                except Exception as e:
                    logger.warning("  [sampler] registration error: %s: %s", type(e).__name__, e)
                finally:
                    self._evo_registered += 1
                    try:
                        self._checkpoint_if_due(population_ref[0], t0)
                    except Exception as e:
                        logger.debug("  [sampler] checkpoint error: %s: %s", type(e).__name__, e)

    def _run_evolution(self, population, n_start, t0):
        remaining_gens = max(0, self.n_pop - n_start)
        target = (
            self.max_sample_nums
            if self.max_sample_nums is not None
            else remaining_gens * self.pop_size
        )
        self._gen_offset = n_start
        self._evo_reserved = 0
        self._evo_registered = 0

        if target <= 0 or not population:
            return population

        self._logger.info(
            f"\n[Evolve]  budget={target} samples  "
            f"samplers={self.num_samplers}  evaluators={self.num_evaluators}"
        )

        population_ref = [population]
        # No point spawning more sampler threads than there are samples to draw.
        n_threads = max(1, min(self.num_samplers, target))
        threads = [
            threading.Thread(
                target=self._sampler_worker,
                args=(population_ref, target, t0),
                name=f"eoh-sampler-{i}",
                daemon=True,
            )
            for i in range(n_threads)
        ]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        # Persist the final population unconditionally — the periodic checkpoint
        # only fires on pop_size boundaries, so a budget that is not a multiple
        # of pop_size would otherwise leave the last samples unsaved.
        final_pop = population_ref[0]
        if final_pop:
            final_gen = self._gen_offset + -(-self._evo_registered // self.pop_size)  # ceil div
            self._save(final_pop, final_gen)
        return final_pop

    def _checkpoint_if_due(self, population, t0):
        """Save a checkpoint and log progress every pop_size completed samples.

        Must be called while holding self._lock. Approximates the old
        per-generation cadence in the asynchronous pipeline.
        """
        if self._evo_registered % self.pop_size != 0:
            return
        gen = self._gen_offset + self._evo_registered // self.pop_size
        if population:
            self._save(population, gen)
        elapsed = (time.time() - t0) / 60
        best = population[0]['objective'] if population else 'N/A'
        self._logger.info(
            f"  --- ~gen {gen}/{self.n_pop}  pop={len(population)}  best={best}  "
            f"samples={self._sample_count}  elapsed={elapsed:.1f}m"
        )
        # 自适应早停:记录本代 best-so-far,最近 stop_window 代改进不足则置停止标志
        if self._adaptive_stop:
            self._gen_best_hist.append(self._best_obj)
            if not self._stop and _should_stop(self._gen_best_hist, self._stop_window, self._stop_min_gap):
                self._stop = True
                self._logger.info(
                    f"  [adaptive-stop] best-so-far 最近 {self._stop_window} 代相对改进 "
                    f"< {self._stop_min_gap:.2%},在 ~gen {gen} 停止进化。"
                )

    # ── initialisation ────────────────────────────────────────────────────────

    def _init_population(self, t0):
        cfg = self.config

        if cfg.use_seed:
            try:
                with open(cfg.seed_path, encoding='utf-8') as f:
                    seeds = json.load(f)
            except FileNotFoundError:
                raise FileNotFoundError(f"Seed file not found: {cfg.seed_path!r}") from None
            except (OSError, json.JSONDecodeError) as e:
                raise RuntimeError(f"Failed to load seed file {cfg.seed_path!r}: {e}") from e
            population = self.evolution.evaluate_seeds(seeds)
            if not population:
                raise RuntimeError("Seed initialization produced no valid individuals.")
            # 用种子种群的最优目标值初始化 best-so-far,使早停判据与逐代轨迹从种子水平起算。
            seed_objs = [ind['objective'] for ind in population if ind.get('objective') is not None]
            if seed_objs:
                self._best_obj = min(seed_objs)
                self._logger.info(f"  Seeded best_obj={self._best_obj} from {len(seed_objs)} seed(s)")
            self._save_checkpoint(population, 0)
            return population, 0

        if cfg.use_continue:
            self._logger.info(f"Resuming from {cfg.continue_path}")
            try:
                with open(cfg.continue_path, encoding='utf-8') as f:
                    population = json.load(f)
            except FileNotFoundError:
                raise FileNotFoundError(f"Continue file not found: {cfg.continue_path!r}") from None
            except (OSError, json.JSONDecodeError) as e:
                raise RuntimeError(f"Failed to load continue file {cfg.continue_path!r}: {e}") from e
            # Seed best-tracker from the loaded population so samples_best.json
            # is only overwritten when a genuinely better individual is found.
            valid_objs = [ind['objective'] for ind in population if ind.get('objective') is not None]
            if valid_objs:
                self._best_obj = min(valid_objs)
                self._logger.info(f"  Restored best_obj={self._best_obj} from checkpoint population")
            n_start = cfg.continue_id
            if not isinstance(n_start, int) or n_start < 0 or n_start > self.n_pop:
                self._logger.warning(
                    "  continue_id=%r out of range [0, %d] — clamping.", n_start, self.n_pop
                )
                n_start = max(0, min(int(n_start) if isinstance(n_start, (int, float)) else 0, self.n_pop))
            if n_start >= self.n_pop:
                self._logger.warning(
                    "  continue_id (%d) >= n_pop (%d): no evolution generations remain.",
                    n_start, self.n_pop
                )
            return population, n_start

        n_init = 2 * self.pop_size
        self._logger.info(
            f"\n[Init]  ({n_init} samples → pop={self.pop_size})  "
            f"samplers={self.num_samplers}  evaluators={self.num_evaluators}"
        )
        raw_population = []
        # Generate the initial 2×pop_size samples concurrently. Each task uses
        # the 'i1' operator (no parents) and the shared evaluation pool.
        with ThreadPoolExecutor(
            max_workers=max(1, min(self.num_samplers, n_init)), thread_name_prefix="eoh-init"
        ) as init_pool:
            futures = [init_pool.submit(self._build_offspring, [], 'i1') for _ in range(n_init)]
            for fut in as_completed(futures):
                try:
                    ind = fut.result()
                except Exception as e:
                    logger.warning("  [init] sample failed: %s: %s", type(e).__name__, e)
                    ind = None
                with self._lock:
                    self._record('i1', ind)
                if ind and ind['objective'] is not None:
                    raw_population.append(ind)

        population = population_management(raw_population, self.pop_size)
        if not population:
            raise RuntimeError(
                "Initial population is empty. Check LLM connectivity, API credentials, "
                "and that evaluate_program() returns a valid float."
            )
        elapsed = (time.time() - t0) / 60
        self._logger.info(
            f"  Init done: {len(raw_population)}/{self._sample_count} evaluated"
            f"  pop={len(population)}  best={population[0]['objective']}  elapsed={elapsed:.1f}m"
        )
        self._save_checkpoint(population, 0)
        return population, 0

    # ── save ──────────────────────────────────────────────────────────────────

    def _save_checkpoint(self, population, gen):
        path = os.path.join(self.output_path, "results", "pops", f"population_generation_{gen}.json")
        try:
            with open(path, 'w') as f:
                json.dump(population, f, indent=4)
        except OSError as e:
            self._logger.warning("Could not save checkpoint to %s: %s", path, e)

    def _save(self, population, gen):
        self._save_checkpoint(population, gen)
        best_path = os.path.join(self.output_path, "results", "pops_best", f"population_generation_{gen}.json")
        try:
            with open(best_path, 'w') as f:
                json.dump(population[0], f, indent=4)
        except OSError as e:
            self._logger.warning("Could not save best individual to %s: %s", best_path, e)
