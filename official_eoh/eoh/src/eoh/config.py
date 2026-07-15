# Copyright (c) 2026 Fei Liu. MIT License.
# Project: https://github.com/FeiLiu36/EoH
# Citation: Fei Liu, Xialiang Tong, Mingxuan Yuan, Xi Lin, Fu Luo, Zhenkun Wang, Zhichao Lu,
#           Qingfu Zhang, Evolution of Heuristics: Towards Efficient Automatic Algorithm Design
#           Using Large Language Model, Forty-first International Conference on Machine Learning
#           (ICML), 2024.

import warnings
from dataclasses import dataclass, field


@dataclass
class LLMConfig:
    api_endpoint: str = None
    api_key: str = None
    model: str = None
    use_local: bool = False
    local_url: str = None
    timeout: int = 180


@dataclass
class EoHConfig:
    """Internal config — users interact with EoH() directly."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    pop_size: int = 5
    n_pop: int = 20
    operators: list = field(default_factory=lambda: ['e1', 'e2', 'm1', 'm2'])
    operator_weights: list = None
    n_parents: int = 2
    # legacy 保持论文实现；objective_aware 反馈总目标；后两种逐步加入尺度和稳定性反馈。
    feedback_policy: str = "legacy"
    # Async pipeline concurrency (decoupled from pop_size).
    # num_samplers : concurrent LLM-generation threads (I/O bound).
    # num_evaluators: concurrent evaluation workers (CPU bound, each isolated
    #                 in a hard-timeout subprocess).
    # max_sample_nums: total evolution-sample budget; None → n_pop * pop_size.
    num_samplers: int = 1
    num_evaluators: int = 1
    max_sample_nums: int = None
    output_dir: str = "./"
    debug: bool = False
    use_seed: bool = False
    seed_path: str = "./seeds/seeds.json"
    use_continue: bool = False
    continue_path: str = "./results/pops/population_generation_0.json"
    continue_id: int = 0
    # Adaptive early-stop (opt-in; disabled by default so fixed-generation runs
    # and baseline reproduction are unaffected). When adaptive_stop is True and
    # the best-so-far objective improves by less than stop_min_gap (relative)
    # over the last stop_window generation checkpoints, evolution stops before
    # the n_pop cap.
    adaptive_stop: bool = False
    stop_window: int = 5
    stop_min_gap: float = 0.0

    def __post_init__(self):
        if self.operator_weights is None:
            self.operator_weights = [1.0] * len(self.operators)
        if len(self.operator_weights) != len(self.operators):
            warnings.warn("operator_weights length mismatch, resetting to uniform.")
            self.operator_weights = [1.0] * len(self.operators)
        if self.n_parents > self.pop_size or self.n_parents < 2:
            warnings.warn("n_parents out of range, resetting to 2.")
            self.n_parents = 2
        if self.feedback_policy not in {
            "legacy",
            "objective_aware",
            "scale_aware",
            "robust_aware",
            "confirmation_aware",
        }:
            warnings.warn("unknown feedback_policy, resetting to legacy.")
            self.feedback_policy = "legacy"
