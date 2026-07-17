# Examples

All requests use the locally running API at `http://127.0.0.1:8000`.

## Compose a Harmonic Progression

```bash
curl -X POST http://127.0.0.1:8000/api/compose/harmony \
  -H 'content-type: application/json' \
  -d '{"factors":[1,3,5,7],"choose":2,"length":8,"seed":42}'
```

## Generate a Euclidean Rhythm

```bash
curl -X POST http://127.0.0.1:8000/api/rhythm/euclidean \
  -H 'content-type: application/json' \
  -d '{"steps":13,"pulses":5,"rotation":2}'
```

## Render a WAV File

```bash
curl -X POST http://127.0.0.1:8000/api/render/wav \
  -H 'content-type: application/json' \
  -d '{"events":[{"ratio":"3/2","start_seconds":0,"duration_seconds":1}]}' \
  --output composition.wav
```

## Live Transport

Connect a WebSocket client to `/api/ws/transport` and send
`{"command":"play"}`, `{"command":"pause"}`, `{"command":"stop"}`, or
`{"command":"improvise","seed":42}`.

## Generate Bass and Melody over a Progression

```bash
curl -X POST http://127.0.0.1:8000/api/compose/bass \
  -H 'content-type: application/json' \
  -d '{"chords":[["3/2","9/8"],["5/4","15/8"]],"strategy":"hybrid"}'

curl -X POST http://127.0.0.1:8000/api/compose/melody \
  -H 'content-type: application/json' \
  -d '{"chords":[["3/2","9/8"],["5/4","15/8"]],"voice_count":1,"seed":42,"contour":"arch"}'
```

## Export a Euclidean Rhythm as MIDI

```bash
curl -X POST http://127.0.0.1:8000/api/export/rhythm/midi \
  -H 'content-type: application/json' \
  -d '{"pattern":[1,0,1,0,0,1,0,0,1,0,1,0,0],"note":36,"steps_per_beat":4}' \
  --output rhythm.mid
```

## Render a WAV Asynchronously

```bash
JOB=$(curl -s -X POST http://127.0.0.1:8000/api/render/jobs \
  -H 'content-type: application/json' \
  -d '{"events":[{"ratio":"3/2","start_seconds":0,"duration_seconds":1}]}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["job_id"])')

curl -s http://127.0.0.1:8000/api/render/jobs/$JOB        # poll status
curl -s http://127.0.0.1:8000/api/render/jobs/$JOB/audio --output composition.wav
```

## Traverse the Harmonic Graph

```bash
curl -X POST http://127.0.0.1:8000/api/harmonic-graph \
  -H 'content-type: application/json' \
  -d '{"factors":[1,3,5,7],"choose":2,"operation":"weighted_walk","steps":12,"seed":42,"metric":"harmonic"}'
```
