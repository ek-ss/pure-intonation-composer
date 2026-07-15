# REST API Specification

**Project:** Pure Intonation Composer

Version: 0.1

---

# 1. Overview

This document defines the public REST API.

All endpoints return JSON unless otherwise specified.

The API follows REST principles while exposing musical operations rather than database entities.

Base URL

```
/api/v1
```

---

# 2. Common Response

Success

```json
{
  "success": true,
  "data": {}
}
```

Error

```json
{
  "success": false,
  "error": {
    "code": "INVALID_RATIO",
    "message": "Denominator must be positive."
  }
}
```

---

# 3. Scale API

## POST /scale/cps

Generate a Combination Product Set.

Request

```json
{
  "numbers":[1,3,5,7,9,11],
  "k":3,
  "harmonic":true,
  "normalize":true
}
```

Response

```json
{
  "ratios":[...]
}
```

---

## POST /scale/euler

Generate an Euler–Fokker genus.

Request

```json
{
  "max3":3,
  "max5":2,
  "max7":1
}
```

---

## POST /scale/import

Import Scala file.

---

## GET /scale/{id}

Load saved scale.

---

# 4. Graph API

## POST /graph/build

Create Johnson graph.

Request

```json
{
  "scale_id":"..."
}
```

Response

```json
{
  "nodes":120,
  "edges":360
}
```

---

## GET /graph/{id}

Return graph.

---

## POST /graph/random-walk

Request

```json
{
  "graph":"...",
  "steps":128,
  "seed":1234
}
```

Response

```json
{
  "path":[...]
}
```

---

## POST /graph/shortest-path

Request

```json
{
  "source":"...",
  "target":"..."
}
```

---

# 5. Harmony API

## POST /harmony/generate

Generate harmonic progression.

Parameters

* graph
* strategy
* randomness
* density

---

## POST /harmony/analyze

Return

* harmonic complexity
* average movement
* entropy
* repeated states

---

# 6. Bass API

## POST /bass/generate

Request

```json
{
  "strategy":"mirror",
  "progression":"..."
}
```

Strategies

mirror

root

fifth

walker

hybrid

---

# 7. Melody API

## POST /melody/generate

Parameters

instrument

register

voice_count

phrase_length

seed

---

# 8. Rhythm API

## POST /rhythm/euclidean

Generate Euclidean rhythm.

---

## POST /rhythm/state-graph

Generate drum graph.

---

## POST /rhythm/phase

Apply phase shifting.

---

# 9. Drum API

## POST /drums/generate

Produces

Kick

Snare

Hat

Percussion

---

## POST /drums/humanize

Random timing

Velocity

Probability

---

# 10. Form API

## POST /form/generate

Supported

ABA

ABACA

Minimal

Continuous

Custom

---

# 11. Composition API

## POST /compose

This endpoint generates an entire composition.

Input

Scale

Harmony

Bass

Melody

Rhythm

Form

Seed

Output

Composition ID

---

## GET /composition/{id}

Return full composition.

---

# 12. Audio API

## POST /render

Starts rendering.

Response

```json
{
 "job":"..."
}
```

---

## GET /render/{job}

Returns

Queued

Running

Finished

Failed

---

## GET /render/{job}/wav

Download WAV.

---

## GET /render/{job}/midi

Download MIDI.

---

## GET /render/{job}/scala

Download Scala tuning.

---

# 13. Analysis API

## POST /analysis/cent

Cent calculations.

---

## POST /analysis/monzo

Monzo decomposition.

---

## POST /analysis/harmonic-distance

Return pairwise distances.

---

## POST /analysis/statistics

Returns

Mean complexity

Pitch histogram

Register histogram

Entropy

---

# 14. Preset API

Create

Update

Delete

Instrument presets.

---

# 15. Project API

Save

Load

Duplicate

Delete

Projects.

---

# 16. Job API

Long-running operations are asynchronous.

Status

Queued

Running

Finished

Failed

Cancelled

Progress

0–100%

---

# 17. Streaming API

Optional Server-Sent Events.

```
GET /events
```

Streams

Render progress

Playback position

Graph updates

---

# 18. Authentication

Version 0.1

None

Future

JWT

OAuth

---

# 19. Versioning

All endpoints include

```
/api/v1
```

Future breaking changes require

```
/api/v2
```

---

# 20. OpenAPI

FastAPI automatically generates

```
/docs
```

Swagger UI

and

```
/redoc
```

ReDoc documentation.
