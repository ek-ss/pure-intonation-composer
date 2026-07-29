# Motif Development to Vital Pack Arrangement

## Status

Implemented MVP at `POST /api/compose/motif-vital-pack`, with browser transfer
from `/motif-development` to `/vital-pack-composer`.

The selected Development Tree is the source of thematic identity. Vital Pack
continues to own form length, profile metadata, automation, tuning timelines,
MPE MIDI, and DAW-facing exports.

## Implemented Flow

1. Generate and develop a motif on the Motif Development page.
2. Check one or more Exploration Candidates for transfer. With no checks, the
   currently auditioned candidate is used.
3. Select **Send Development Tree to Vital Pack**. Each selected motif receives
   its own deterministic Development Tree.
4. Vital Pack receives the selected node sequences through browser-local
   transfer and generates a song plan automatically.
5. Export the resulting project JSON, MPE MIDI, Scala base, tuning/MTS-style
   timelines, sidechain envelope, or REAPER manifest from Vital Pack.

## Variable Form Mapping

Vital Pack accepts 3–12 sections. The canonical seven-part form uses the
mapping below. Shorter forms select representative phases; longer forms repeat
middle phases with unique labels while retaining canonical energy and
instrument templates.

| Canonical Vital Pack section | Preferred Development Tree role |
| --- | --- |
| Intro | `theme` |
| A | `theme` |
| Build | `build` |
| Drop 1 | `climax` |
| Break | `development` |
| Final Drop | `recapitulation` |
| Outro | `coda` |

When a preferred role is unavailable, the adapter uses the next Tree node in
a deterministic order. Each section records its selected `motif_id`, formal
role, and target chord in `motif_arrangement.section_assignments`.

## Instrument Mapping

- PI01, PI02, PI03, and PI08: target-chord sustain voicings;
- PI04: repeated transformed motif as the lead line;
- PI05: target-chord root bass;
- PI06: terminal-motif accents;
- PI07: motif-onset pulse;
- DRUMS: kick/snare grid with hats and accents derived from motif onsets.

All generated events include motif provenance where applicable: `motif_id`,
`formal_role`, `target_chord`, and, for pitched motif roles,
`source_note_index`, `transformation_chain`, and `identity_retention`.
`source_motif_id` distinguishes multiple selected candidates.

## Repetition Development

`development_amount` ranges from 0 to 1. At zero, a motif repeats unchanged.
Higher values progressively enable deterministic cyclic rotation,
chord-tone transposition, pitch retrograde, selective chord projection, and
small rhythmic displacement. Repetitions can also rotate through multiple
transferred motif sources while keeping the section's target chord stable.

Every note records its repetition number and applied
`development_operations`. Quality output reports the number of source motifs
and distinct development operations.

## Motif Phase Shift

The arrangement can add a second motif lane over the same section harmony.
PI04 is lane A and PI07 is lane B. Lane B can use another selected motif or a
different variation of the same source.

- `off`: ordinary motif pulse;
- `static`: fixed beat offset;
- `progressive`: offset changes on every bar;
- `polymetric`: repeating offset schedule with a 15:16 time scale.

`phase_shift_beats`, `phase_shift_increment`, and
`phase_shift_cycle_bars` control the process. JSON output retains the complete
phase schedule, lane IDs, overlap ratio, and phase-distinctness quality gate.

## Current Boundary

The current release regenerates an entire motif arrangement when the seed is
changed. Existing Vital Pack's scope-specific section regeneration remains
available for ordinary Vital Pack plans. Per-section motif locks and
independent harmony/rhythm/orchestration regeneration are the next extension.

The transfer is browser-local, not persistent project storage. Project JSON
retains the complete generated arrangement and its motif provenance, while
project JSON import is still outside the current project boundary.

## Follow-up Work

- selectable Tree branches and per-section node overrides;
- user-edited section names, weights, energy curves, and role assignments;
- per-part role selection beyond the default PI04 lead mapping;
- motif-aware section-level regeneration and quality ranking;
- convergent phase anchors and independent chord clocks;
- persistent project IDs and cross-device transfer;
- browser interaction and audio regression coverage.
