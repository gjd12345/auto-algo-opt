"""Entry point for a single official EOH run; delegates to eoh_single_runner."""
from eoh_rag.experiments.eoh_single_runner import *  # noqa: F401,F403
from eoh_rag.experiments.eoh_single_runner import main

if __name__ == "__main__":
    main()
