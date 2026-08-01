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
| [harmonic_pitch_circle.md](harmonic_pitch_circle.md) | Implemented fifth-step chord-shape study page and G12 boundary |
| [development_plan_prime_limit_harmonic_explorer.md](development_plan_prime_limit_harmonic_explorer.md) | Implemented G12 core and remaining prime-lattice explorer roadmap |
| [minimal_functional_harmony_composer.md](minimal_functional_harmony_composer.md) | Implemented T/S/D minimal-process composer MVP and its explicit boundary |
| [vital_pack_composer.md](vital_pack_composer.md) | Implemented Vital Pack Composer MVP and its DAW/export boundary |
| [motif_vital_arrangement.md](motif_vital_arrangement.md) | Implemented Development Tree to Vital Pack song-arrangement bridge |
| [composition_explorer.md](composition_explorer.md) | Implemented instrument-constrained multi-candidate composition explorer |
| [development_plan_motif_development_engine.md](development_plan_motif_development_engine.md) | Proposed G14 motif generation, variation, and formal-development specification |

## Roadmaps

| Document | Scope |
| --- | --- |
| [development_plan.md](development_plan.md) | Active functional roadmap and G9-G13 overview |
| [development_plan_prime_limit_harmonic_explorer.md](development_plan_prime_limit_harmonic_explorer.md) | Experimental prime-lattice scale explorer and planned chord/progression work |
| [development_plan_genre_arrangement.md](development_plan_genre_arrangement.md) | Planned genre-guided harmony, parts, MIDI/JSON, and rendering pipeline |
| [development_plan_harmonic_phase_shift.md](development_plan_harmonic_phase_shift.md) | Planned dual-rhythm, same-progression harmonic phase composition |
| [development_plan_motif_development_engine.md](development_plan_motif_development_engine.md) | Planned anchor-chord motif generator and section-scale variation engine |
| [motif_vital_arrangement.md](motif_vital_arrangement.md) | Implemented G14-to-Vital arrangement boundary and follow-up roadmap |
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
