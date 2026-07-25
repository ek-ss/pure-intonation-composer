# Documentation

This directory separates current behavior from design proposals and historical
roadmaps. Start with the first table rather than treating every specification
as implemented.

## Start Here

| Document | Purpose |
| --- | --- |
| [status.md](status.md) | Canonical implementation status, known gaps, and next priorities |
| [usage_ja.md](usage_ja.md) | Japanese workbench and workflow guide |
| [usage.md](usage.md) | English workbench and workflow guide |
| [examples.md](examples.md) | Runnable API examples |
| [api.md](api.md) | Implemented REST and WebSocket API reference |

## Technical Reference

| Document | Scope |
| --- | --- |
| [data_model.md](data_model.md) | Conceptual data model; planned models are labelled |
| [algorithm.md](algorithm.md) | Composition algorithm specification, including future research |
| [algorithm_rhythm.md](algorithm_rhythm.md) | Drum alignment and phase-shift design |
| [visualization.md](visualization.md) | Implemented reference-node layered graph layout |

## Roadmaps

| Document | Scope |
| --- | --- |
| [development_plan.md](development_plan.md) | Active functional roadmap and G9-G11 overview |
| [development_plan_genre_arrangement.md](development_plan_genre_arrangement.md) | Planned genre-guided harmony, parts, MIDI/JSON, and rendering pipeline |
| [development_plan_rhythm.md](development_plan_rhythm.md) | Original rhythm milestone plan; retained as design history |

`status.md` is the source of truth when a roadmap or design document and the
current code disagree. The live OpenAPI schema at `/docs` is authoritative for
request and response validation.

## Source Boundaries

- `backend/app/` is the canonical application source.
- `backend/tests/` is the automated behavior inventory.
- `backend/app/static/` is the browser workbench source.
- `backend/build/lib/` is a generated packaging artifact and may lag behind
  `backend/app/`; do not use it to determine implementation status.
