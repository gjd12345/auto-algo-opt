from __future__ import annotations

import ast
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

from eoh_rag.experiments.batch_runner import _build_cmd, _validate_manifest


REPO_ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_SRC = REPO_ROOT / "official_eoh" / "eoh" / "src"
if str(OFFICIAL_SRC) not in sys.path:
    sys.path.insert(0, str(OFFICIAL_SRC))

from eoh.eoh.evolution import Evolution, numeric_constant_mutations  # noqa: E402


PARENT_CODE = """def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    penalty = 1.0 / (residual ** 2 + 1e-9)
    peak = np.exp(-((residual / (bins.mean() + 1e-9) - 0.45) ** 2) * 10)
    return penalty + peak
"""


def _numeric_values(code: str) -> list[int | float]:
    return [
        node.value
        for node in ast.walk(ast.parse(code))
        if isinstance(node, ast.Constant)
        and not isinstance(node.value, bool)
        and isinstance(node.value, (int, float))
    ]


def test_numeric_constant_mutations_change_one_literal_and_keep_stability_terms() -> None:
    mutations = numeric_constant_mutations(PARENT_CODE)

    # 两个平方指数、一个 0.45 和一个 10 各自展开邻域，共得到 16 个唯一候选。
    assert len(mutations) == 16
    assert len({code for code, _ in mutations}) == len(mutations)
    parent_values = _numeric_values(PARENT_CODE)
    for code, description in mutations:
        child_values = _numeric_values(code)
        assert len(child_values) == len(parent_values)
        assert sum(left != right for left, right in zip(parent_values, child_values)) == 1
        assert code.count("1e-09") == 2
        assert description.startswith("Numeric neighborhood mutation:")


def test_n1_uses_best_parent_without_calling_llm() -> None:
    evolution = Evolution.__new__(Evolution)
    evolution.feedback_policy = "confirmation_gate_only"
    evolution.n_parents = 2
    evolution._numeric_mutation_cursor = 0
    evolution._numeric_mutation_lock = threading.Lock()
    evolution._call_llm = lambda _prompt: (_ for _ in ()).throw(AssertionError("LLM called"))
    population = [
        {"objective": 0.4, "code": "def score(x):\n    return x * 3", "algorithm": "worse"},
        {"objective": 0.2, "code": "def score(x):\n    return x * 2", "algorithm": "best"},
    ]

    parent, first_code, first_algorithm = evolution._generate(population, "n1")
    _, second_code, _ = evolution._generate(population, "n1")

    assert parent["algorithm"] == "best"
    assert first_code != second_code
    assert first_algorithm.startswith("Numeric neighborhood mutation:")


def test_n1_only_evolution_does_not_initialize_llm(monkeypatch) -> None:
    import eoh.eoh.evolution as evolution_module

    monkeypatch.setattr(
        evolution_module,
        "InterfaceLLM",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("LLM initialized")),
    )
    config = SimpleNamespace(
        debug=False,
        n_parents=2,
        feedback_policy="confirmation_gate_only",
        operators=["n1"],
        llm=SimpleNamespace(
            api_endpoint=None,
            api_key=None,
            model=None,
            use_local=False,
            local_url=None,
            timeout=1,
        ),
    )
    problem = SimpleNamespace(
        task_description="offline test",
        template_program="def score(x):\n    return x",
        n_processes=1,
        timeout=1,
    )

    evolution = Evolution(config, problem)

    assert evolution.llm is None


def test_numeric_neighborhood_proxy_is_single_run_and_offline() -> None:
    manifest = json.loads(
        (
            REPO_ROOT
            / "eoh_rag_workspace/experiments/manifests/bp_numeric_neighborhood_proxy_v1.json"
        ).read_text(encoding="utf-8")
    )

    assert _validate_manifest(manifest) == []
    assert manifest["operators"] == "n1"
    assert manifest["generations"] == [4]
    assert manifest["pop_size"] == 4
    assert manifest["max_runs"] == 1
    assert manifest["discovery_contract"]["llm_calls"] == 0
    command = _build_cmd(manifest, "bp_online", manifest["arms"][0], 4, 0, "out")
    assert command[command.index("--operators") + 1] == "n1"
    assert command[command.index("--llm-model") + 1] == "offline-n1"
