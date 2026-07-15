# Pure Intonation Workbench — Backend

FastAPI backend for generating and analysing rational tunings.

## Run

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API documentation.

## Included endpoints

- `POST /api/cps` — Combination Product Set generation
- `POST /api/euler-fokker` — Euler–Fokker genus generation
- `POST /api/harmonic-series` and `/api/subharmonic-series`
- `POST /api/analyze-ratio` — cents and sparse prime-exponent monzo
- `POST /api/harmonic-graph` — CPS Johnson graph and deterministic traversals
- `POST /api/compose/harmony` — deterministic, connected CPS chord progressions
- `POST /api/compose/voice-leading` — compact, non-crossing rational voicings
- `POST /api/compose/bass` — continuous root, fifth, and mirror bass lines
- `POST /api/compose/melody` — independent contour-controlled melodic voices
- `POST /api/export/scala` — Scala `.scl` content

## Example

```bash
curl -X POST http://127.0.0.1:8000/api/cps \
  -H 'content-type: application/json' \
  -d '{"factors":[1,3,5,7],"choose":2,"kind":"harmonic"}'
```

## Harmonic graph example

`POST /api/harmonic-graph` represents each CPS factor subset as a node in the
Johnson graph `J(n, k)`. Select `shortest_path`, `random_walk`, or
`weighted_walk` with a `seed` to receive a reproducible traversal.

```json
{"factors":[1,3,5,7],"choose":2,"operation":"weighted_walk","steps":8,"seed":42,"metric":"harmonic"}
```

## Harmony composition example

The harmony generator walks only along Johnson graph edges, so every adjacent
pair of generated chords is connected. With the same input and `seed`, it
always returns the same progression.

```json
{"factors":[1,3,5,7],"choose":2,"length":8,"seed":42,"metric":"harmonic"}
```

## Voice leading example

`POST /api/compose/voice-leading` arranges equal-size chord sequences inside a
cent-based register. It minimizes movement while enforcing a per-voice leap
limit and non-crossing voice order.

```json
{"chords":[["1/1","5/4","3/2"],["9/8","4/3","5/3"]],"max_leap_cents":300}
```
