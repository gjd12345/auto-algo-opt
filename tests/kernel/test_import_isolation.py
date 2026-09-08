from __future__ import annotations

import sys


def test_importing_kernel_does_not_load_fme_or_official_eoh():
    forbidden = [name for name in sys.modules if name == "eoh" or name.startswith("eoh_rag.fme") or name.startswith("eoh.eoh")]
    # Import after snapshot of accidental preloads from other tests in this directory.
    import agent_skill_loop
    import agent_skill_loop.loop
    import agent_skill_loop.generator
    import agent_skill_loop.evaluator

    assert agent_skill_loop.__name__ == "agent_skill_loop"
    loaded = [name for name in sys.modules if name == "eoh" or name.startswith("eoh_rag.fme") or name.startswith("eoh.eoh")]
    assert loaded == forbidden
    from pathlib import Path
    generator = Path(agent_skill_loop.generator.__file__).read_text(encoding="utf-8")
    assert "fme_aware" not in generator
    assert "from eoh" not in generator
    assert "eoh_rag.fme" not in generator
    evaluator = Path(agent_skill_loop.evaluator.__file__).read_text(encoding="utf-8")
    assert "official_eoh" not in evaluator
    assert "eoh_rag.fme" not in evaluator
    import eoh_frozen.export  # noqa: F401

    after_export = [name for name in sys.modules if name == "eoh" or name.startswith("eoh_rag.fme") or name.startswith("eoh.eoh")]
    assert after_export == forbidden
