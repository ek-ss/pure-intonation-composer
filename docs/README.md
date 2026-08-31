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
| [vital_fractional_piano.md](vital_fractional_piano.md) | PI22 piano-like Vital preset, builder, integration, and DAW workflow |
| [bohlen_pierce_workbench.md](bohlen_pierce_workbench.md) | Implemented 3:1-equave scale, chord, progression, composition, and export workbench |
| [mixed_meter_drums.md](mixed_meter_drums.md) | Implemented mixed-meter drum form, density, phase, playback, and export workbench |
| [midi_creator_toolkit.md](midi_creator_toolkit.md) | Web MIDI performance capture, exact-ratio motif processing, export, and composer handoff |
| [development_plan_motif_development_engine.md](development_plan_motif_development_engine.md) | Proposed G14 motif generation, variation, and formal-development specification |
| [song_program_spec.md](song_program_spec.md) | Draft searchable composition genotype and deterministic compiler contract |
| [song_program_numeric_contract.md](song_program_numeric_contract.md) | Normative SP0 pitch arithmetic, chord error, complexity, and ranking |
| [song_program_budget_contract.md](song_program_budget_contract.md) | Normative SP0 deterministic operation-budget ledger |
| [arrangement_project_1_2_contract.md](arrangement_project_1_2_contract.md) | Normative SP0 strict Project schema and provenance union |
| [song_program_conformance_pack.md](song_program_conformance_pack.md) | Executable schemas, fixtures, oracle, cache, and cross-process handoff contract |
| [song_program_optimized_resolver_contract.md](song_program_optimized_resolver_contract.md) | GEN0-A exact branch-and-bound and exhaustive-oracle equality contract |
| [song_program_progression_contract.md](song_program_progression_contract.md) | GEN0-B exact progression and voice-correspondence contract |
| [song_program_renderer_evaluation_contract.md](song_program_renderer_evaluation_contract.md) | GEN0-C deterministic renderer, pitch audit, and calibration contract |
| [instrument_catalog_render_manifest_contract.md](instrument_catalog_render_manifest_contract.md) | GEN0-C catalog, immutable assets, release/drum lookup, and render-manifest identity |
| [song_program_search_loop_contract.md](song_program_search_loop_contract.md) | GEN0-D/LLM sampler, descriptors, QD archive, planner, and run-state contract |
| [song_program_search_artifacts_contract.md](song_program_search_artifacts_contract.md) | GEN0-D/LLM closed manifests, mutations, lineage, CAS, records, and replay identity |
| [song_program_capability_compatibility_contract.md](song_program_capability_compatibility_contract.md) | Native 3/1, MIDI/Scala export, projection, legacy, and capability contract |
| [song_program_specification_closure.md](song_program_specification_closure.md) | Authority map, remaining artifacts, future exclusions, and closure rule |
| [adr_song_program.md](adr_song_program.md) | Accepted SongProgram architecture decisions and measurable gates |
| [song_program_review_2026-08-30.md](song_program_review_2026-08-30.md) | Multi-agent freeze review, issue register, and conditional development readiness |
| [multi_agent_design_review.md](multi_agent_design_review.md) | Evidence-based multi-agent design review and arbitration protocol |

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
| [development_plan_llm_lattice_music_loop.md](development_plan_llm_lattice_music_loop.md) | Proposed quality-diversity and LLM-guided lattice-music generation loop |

`status.md` is the source of truth when a roadmap or design document and the
current code disagree. The live OpenAPI schema at `/docs` is authoritative for
request and response validation.

## Source Boundaries

- `backend/app/` is the canonical application source.
- `backend/tests/` is the automated behavior inventory.
- `backend/app/static/` is the browser workbench source.
- `backend/build/lib/` is a generated packaging artifact and may lag behind
  `backend/app/`; do not use it to determine implementation status.
