# Reproducibility Guide

## Prerequisites

- Python >= 3.10
- Go >= 1.20
- Access to an OpenAI-compatible LLM API (DeepSeek, JoyAI, etc.)

## Quick Start (unit tests only)

```bash
pip install -e .
pytest tests/ -v
```

No LLM API key needed for unit tests — they use mocks.

## Environment Variables

| Variable | Required for | Description |
|----------|--------------|-------------|
| `DEEPSEEK_API_KEY` | Real LLM runs | API key for the LLM endpoint |
| `DEEPSEEK_API_ENDPOINT` | Real LLM runs | e.g. `api.deepseek.com` |
| `DEEPSEEK_MODEL` | Real LLM runs | e.g. `deepseek-v4-pro` |
| `EOH_OFFICIAL_ROOT` | Official EOH experiments | Path to cloned EoH-main repo |
| `EOH_OFFICIAL_PYTHON` | Official EOH experiments | Path to python in EOH venv |

Copy `.env.example` and fill in your values:

```bash
cp .env.example .env
# edit .env with your API credentials
```

## Setting Up Official EOH (for real experiments)

The official EOH runner requires a separate checkout and virtual environment:

```bash
# 1. Clone official EOH
git clone <eoh-repo-url> /path/to/EoH-main

# 2. Create and activate venv
python3.10 -m venv /path/to/eoh_official_venv
source /path/to/eoh_official_venv/bin/activate

# 3. Install EOH dependencies (includes torch, numba, etc.)
pip install -r requirements-official-eoh.txt
cd /path/to/EoH-main && pip install -e .

# 4. Set environment variables
export EOH_OFFICIAL_ROOT=/path/to/EoH-main
export EOH_OFFICIAL_PYTHON=/path/to/eoh_official_venv/bin/python
```

## Go Solver

The Go solver compiles from the project root:

```bash
go build -o mainbin main.go routing.go
```

## Running Experiments

### Dry-run (no API calls)

```bash
python -m eoh_rag.experiments.batch_runner \
    --manifest path/to/manifest.json --dry-run
```

### Smoke test (gen=0, 1 run)

Requires `EOH_OFFICIAL_ROOT` and `EOH_OFFICIAL_PYTHON` set:

```bash
python -m eoh_rag.experiments.eoh_single_runner \
    --problem bp_online --arm pure_eoh --generations 0 --pop-size 4
```

## What's NOT needed for unit tests

The following are only needed when running real EOH experiments:

- `requests`, `torch`, `numba`, `python-docx` (Agent_EOH internal deps)
- `EOH_OFFICIAL_ROOT` / `EOH_OFFICIAL_PYTHON` environment variables
- LLM API access
