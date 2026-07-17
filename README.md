# Pure Intonation Composer

Pure Intonation Composer is a deterministic composition workbench for rational
tuning. It generates CPS and Euler-Fokker material, moves through a Johnson
harmonic graph, composes harmony/bass/melody, creates rhythm, renders WAV, and
exports MIDI, Scala, and JSON.

## Features

- **Scale generators** — Combination Product Sets (harmonic/subharmonic),
  Euler–Fokker genera, harmonic and subharmonic series, octave reduction
- **Harmonic graph** — Johnson graph J(n,k) over CPS combinations with
  shortest-path, random-walk, and weighted-walk traversal (harmonic, monzo,
  or cent distance metrics)
- **Composition engines** — seeded harmony progressions, voice leading
  (Hungarian assignment), bass lines (mirror/root/fifth/hybrid strategies),
  and independent melody voices with contour and phrase memory
- **Rhythm engine** — Euclidean rhythms, Hamming-distance state graphs,
  phase shifting across independent cycle lengths, seeded humanization
- **Audio** — offline WAV rendering (sine/triangle/saw/square/additive,
  ADSR, delay, reverb) with an async job queue
- **Export** — MIDI (pitched and GM-percussion rhythm), Scala tuning files,
  structured JSON
- **Browser workbench** — pitch-circle and force-directed graph views with
  walk visualization, WebAudio performance keyboard, real-time timeline
  recorder with replay, compose/rhythm panels, WebSocket transport

All stochastic operations accept a seed and return the same output for the
same input.

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

> Install the package editable (`pip install -e .`). A non-editable install
> leaves a stale copy in site-packages and tests will not see local changes.

## Verification

```bash
cd backend
pytest
ruff check .
mypy app
```

## Project Structure

```
backend/
  app/
    main.py            FastAPI application: REST endpoints + WebSocket transport
    models.py          Pydantic request models
    jobs.py            Async render job queue
    generators/        CPS, Euler–Fokker, harmonic/subharmonic series
    graphs/            Johnson graph + traversal algorithms
    composition/       Harmony, voice leading, bass, melody
    rhythm/            Euclidean, state graph, phase shift, humanize
    audio/             Offline WAV rendering
    exporters/         MIDI (pitched + percussion), Scala
    tuning/            Ratio parsing, cents, monzo analysis
    static/            Browser workbench (vanilla JS, no build step)
  tests/               pytest suite
docs/
  algorithm.md         Musical algorithm design specification
  api.md               Implemented REST/WebSocket API reference
  data_model.md        Canonical data model specification
  development_plan.md  Roadmap, phases, and current status
  examples.md          Copy-paste API usage examples
```

## Documentation

See [docs/examples.md](docs/examples.md) for usage examples and
[docs/development_plan.md](docs/development_plan.md) for the roadmap and
implementation status.
