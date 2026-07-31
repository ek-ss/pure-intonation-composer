# Motif Development to Vital Pack Arrangement

## Status

Implemented MVP at `POST /api/compose/motif-vital-pack`, with browser transfer
from `/motif-development` to `/vital-pack-composer`.

The selected Development Tree is the source of thematic identity. Vital Pack
continues to own form length, profile metadata, automation, tuning timelines,
MPE MIDI, and DAW-facing exports.

The transfer also carries `prime_basis`. A custom subset such as `[3,7,13]`
is preserved in project metadata and constrains the extracted motif scale,
generated chords, transformed stacks, and all pitched Vital events.

Vital tonal controls remain active after transfer. Major mode rewards motif
scale tones near a pure 5/4 third above the selected root; Minor rewards tones
near 6/5. `mode_strength` controls that reward, while
`progression_contrast` expands root motion and relaxes common-tone retention.
No pitch outside the transferred motif scale or selected prime basis is
introduced.

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
- PIANO: independent ascending, descending, turnaround, or zigzag scale runs
  drawn only from the extracted motif scale;
- DRUMS: kick/snare grid with hats and accents derived from motif onsets.

PI04 no longer fills every available bar or repeats until the bar is full.
The selected rest phrasing limits each active bar to one, two, or three motif
statements and schedules silent lead/pulse bars. Motif-derived hats and
percussion follow the PI04 activity decision, while the kick/snare backbone
can continue through a motif breath.

`Piano part` enables the external piano lane. `Piano material` selects either
`Scale run` or `Transferred motif`. Scale runs use the exact fractional-ratio
classes in the extracted motif scale; only their octave placement changes.
Transferred motif mode performs the selected node's developed notes,
including source rests and simultaneous `harmony_tones`. `Piano activity`
controls how often either material enters. `Piano density` controls scale-run
subdivision or the maximum number of motif statements in a bar. Full
motif-breath bars remain silent, and every emitted pitch retains Development
Tree provenance. MIDI export places the events on a separate `PIANO` track
for assignment to a microtonal-capable piano instrument.

All generated events include motif provenance where applicable: `motif_id`,
`formal_role`, `target_chord`, and, for pitched motif roles,
`source_note_index`, `transformation_chain`, and `identity_retention`.
`source_motif_id` distinguishes multiple selected candidates.

When a source step contains `harmony_tones`, PI04 and PI07 emit every stack
voice at the same onset and duration. `stack_voice: 0` is the contour tone;
higher values identify its companion voices. Transposition, retrograde,
target-chord projection, and motif-scale constraint process the complete
stack. The resulting maximum is reported as
`quality.motif_polyphony_max`.

## Motif-Derived Scale and Harmony

The adapter no longer repeats each Development Tree node's original
`target_chord` as a fixed section chord. It extracts octave-normalized pitch
classes from all selected motif nodes, weights accented and exact-anchor notes,
adds the reference tonic, and retains up to 24 tones as the arrangement's
`motif_scale`.

Every bar generates a new three- or four-tone chord from that scale. Ranking
combines:

- pitch prominence in the current motif;
- pure-interval consonance relative to the selected root;
- common-tone retention from the previous chord;
- affinity with the Development Tree target chord;
- section energy, which controls triad versus tetrad density.

The root follows a deterministic motif-tone motion pattern, and an unchanged
chord is replaced when another scale tone is available. PI01, PI02, PI03, and
PI08 use these generated chord tones; PI05 follows the generated root.
Repetition-level motif transformations are snapped back to the same scale.

Project JSON exposes `motif_arrangement.motif_scale`, per-bar `motif_tones`
and `common_tones`, and each section's `generated_chords`. `base_scale` uses
the same ratios, so Scala export describes the actual transferred-motif pitch
material instead of the former fixed seven-tone reference.

Quality gates report motif-scale harmony coverage, event conformance, mean
motif-tone chord coverage, unique chord count, and harmony variety.

## Repetition Development

`development_amount` ranges from 0 to 1. At zero, a motif repeats unchanged.
Higher values progressively enable deterministic cyclic rotation,
chord-tone transposition, pitch retrograde, selective chord projection, and
small rhythmic displacement. Repetitions can also rotate through multiple
transferred motif sources while keeping the section's target chord stable.

Every note records its repetition number and applied
`development_operations`. Quality output reports the number of source motifs
and distinct development operations.

## Rest and Activity Phrasing

Motif Development supplies note-level space by retaining the original onset
grid while shortening each note gate with `rest_density`. These gaps survive
browser audition, Development Tree transformations, JSON, and MIDI.

Vital Pack adds a second, song-level layer with:

- `motif_activity`: target probability for an active motif bar;
- `breathing`: balanced play/rest interlock;
- `sparse`: more unanswered space and one statement per active bar;
- `driving`: denser entries, capped at three statements per active bar.

The seeded activity schedule independently switches PI04 lane A and PI07 lane
B, forces a breath after at most three active bars, and places a full motif
rest every eight bars. In phase-shift mode, lane B can answer during an A
rest rather than merely doubling it.

Project JSON stores every decision in
`motif_arrangement.activity.schedule`. Quality gates expose active ratios,
full-rest bars, maximum consecutive activity, and `motif_breathing_ok`.

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
- editable harmony weights and selectable chord cardinality;
- per-part role selection beyond the default PI04 lead mapping;
- motif-aware section-level regeneration and quality ranking;
- convergent phase anchors and independent chord clocks;
- persistent project IDs and cross-device transfer;
- browser interaction and audio regression coverage.
