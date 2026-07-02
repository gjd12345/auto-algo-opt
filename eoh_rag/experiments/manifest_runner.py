"""Manifest-driven entry point that runs experiment batches via ``batch_runner``."""
from eoh_rag.experiments.batch_runner import *  # noqa: F401,F403
from eoh_rag.experiments.batch_runner import main

if __name__ == "__main__":
    main()
