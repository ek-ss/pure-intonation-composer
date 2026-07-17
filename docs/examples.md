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
