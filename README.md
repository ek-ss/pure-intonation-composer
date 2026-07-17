# Pure Intonation Composer

Pure Intonation Composer is a deterministic composition workbench for rational
tuning. It generates CPS and Euler-Fokker material, moves through a Johnson
harmonic graph, composes harmony/bass/melody, creates rhythm, renders WAV, and
exports MIDI, Scala, and JSON.

## Quick Start

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000` for the workbench and
`http://127.0.0.1:8000/docs` for interactive OpenAPI documentation.

## Verification

```bash
cd backend
pytest
ruff check .
mypy app
```

All stochastic operations accept a seed and return the same output for the
same input. See [examples](docs/examples.md) and the
[development plan](docs/development_plan.md).
