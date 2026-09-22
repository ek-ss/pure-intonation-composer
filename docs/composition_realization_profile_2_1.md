# Composition Realization Profile 2.1

Status: normative design specification, implementation pending.

## 1. Scope

This contract converts an ordered CompositionPlan and its transition plan into varied,
audible part realizations. It supplements, but does not replace, Native JI evaluation,
PIL interpretation, the exact progression resolver or the deterministic reference
renderer.

The contract owns:

1. motif vocabulary and melodic relation realization;
2. multi-lane drum realization;
3. section-conditioned bass patterns and kick coupling;
4. 12-TET-reference functional harmony mapped to lattice chords;
5. density, role-mask and energy-curve realization;
6. role-specific articulation and preview-instrument intent;
7. an optional MIDI/MPE-to-WAV preview path.

It does not make external synth output authoritative. Canonical Program, Project,
reference PCM and existing Native JI/PIL reports remain independently reproducible.

## 2. Processing order

Realization uses this fixed dependency order:

```text
form + transition plan
  -> section role masks and continuous energy/density curves
  -> functional harmony targets
  -> exact lattice chord progression and voicing
  -> drum lane patterns
  -> bass pattern constrained by harmony and selected kick anchors
  -> melody/motif constrained by active chords and phrase function
  -> transition-expression edits
  -> articulation/instrument intent
  -> compile
  -> authoritative reference WAV and optional perceptual preview WAV
```

Later stages may not silently repair an earlier invalid result. Rejection returns to the
smallest owning stage and retains already locked form, motif lineage and harmony plan.

## 3. Motif vocabulary

The initial profile must contain at least eight canonically distinct motif templates,
covering all of these contour families:

```text
ascending
descending
arch
inverted_arch
neighbor_return
leap_and_step_return
syncopated_repetition
pickup_to_cadence
```

Each template declares two or four bars, four to sixteen events, normalized onset and
duration, accent, contour delta and phrase-role tags. Two templates are distinct only if
their audible event payload differs; changing an ID or weight is insufficient.

### 3.1 Pitch-relation vocabulary

The fixed `[0, 1, 2]` chord-member cycle is removed. Every motif event instead declares
one closed relation:

| Relation | Payload | Realization |
| --- | --- | --- |
| `chord_role` | `root`, `third`, `fifth`, `extension`, `any` | Select the matching resolved chord voice |
| `member_sequence` | bounded list of target ordinals | Follow the declared phrase-local sequence |
| `nearest_member` | contour direction and maximum ordinal distance | Choose the closest active chord voice satisfying the contour |
| `common_tone` | previous-event preference | Prefer a voice shared with the preceding chord |
| `approach` | target role, direction, lattice step limit | Approach a target chord voice before its onset |
| `passing` | two target roles and intermediate-count bound | Insert a bounded lattice path between chord voices |
| `neighbor` | target role and return delay | Leave and return to the same chord role |
| `cadence_tone` | `root`, `third`, `fifth` | Force the final phrase event to the declared terminal role |

`approach`, `passing` and `neighbor` remain lattice-native. A reference scale degree may
guide direction, but emitted pitches must resolve to canonical lattice vectors and ratios.

### 3.2 Register and contour

Every foreground phrase declares:

```text
register_start
register_peak
register_end
peak_position_q
maximum_event_leap_mc
pickup_policy
cadence_tone_policy
```

The register arc is piecewise linear in millicents and acts as a target, not a hard pitch
replacement. Candidate chord members are scored by distance to the arc, contour
continuity, requested chord role and lattice complexity. Stable tuple ordering breaks
ties. A phrase that cannot satisfy range or leap constraints fails rather than collapsing
all events to one member cycle.

## 4. Drum lanes

`drums` is a coordinated role containing these required lanes:

```text
kick
snare
clap
closed_hat
open_hat
fill
```

The initial note identities are 36, 38, 39, 42, 46 and the bounded set
`[41, 43, 45, 47, 48, 50]` for fill events. Instrument catalogs may map them to different
assets, but missing required note maps are a hard preview-render failure.

Each section function selects a profile-owned drum-pattern family:

| Function | Required behavior |
| --- | --- |
| opening | sparse kick or hat; snare/clap may enter after the midpoint |
| statement | stable kick/snare backbeat with bounded hat variation |
| preparation | non-decreasing hat subdivision or fill intensity toward the boundary |
| arrival | full kick/snare/clap pattern with an explicit boundary impact option |
| contrast | reduced kick density or removed kick, while retaining a timing reference |
| return | recognizable prior groove plus one bounded variation |
| closure | non-increasing lane count and a declared terminal hit or tail |

Fill events belong to transition expression and may replace, not merely overlay, ordinary
lane events inside the pre-boundary window.

## 5. Bass realization

Bass patterns are selected by section function and may not use one global two-onset cell.
The initial closed pattern vocabulary contains:

```text
whole_root
half_root
kick_unison
syncopated_answer
eighth_drive
pickup_walk
sustain_dropout
cadential_root
```

Every pattern declares candidate onsets, gates, pitch-role sequence and kick-coupling mode:

| Coupling mode | Rule |
| --- | --- |
| `exact_subset` | every bass onset must coincide with a selected kick anchor |
| `anchor_plus_answer` | at least half of bass onsets are kick-aligned; remaining onsets answer within a bounded delay |
| `independent_with_downbeat` | the first downbeat is aligned; later onsets may diverge |
| `dropout` | no new bass onset is emitted in the declared window |

The selected mode is conditioned on the section function and transition class. Arrival
defaults to `exact_subset` or `anchor_plus_answer`; contrast and closure may use
`independent_with_downbeat` or `dropout`. Pitch targets follow the active lattice chord's
root/common tone/path; they are not inferred from kick notes.

## 6. Functional harmony with a 12-TET reference

12-TET is a reference relationship layer, not the emitted tuning. The initial profile
contains functional progression templates commonly recognizable through 12-TET chord
relationships, including at least:

```text
I - V - vi - IV
I - vi - IV - V
vi - IV - I - V
I - IV - V - I
ii - V - I
I - iii - IV - V
I - V/V - V - I
I - bVII - IV - I
```

Templates are abstract and declare scale-degree root, chord quality, inversion options,
duration, functional label and cadence role. The profile may add genre-specific templates
without changing the resolver.

### 6.1 Lattice mapping

For every reference chord occurrence:

1. convert each 12-TET chord member to a target ordinal and target millicents relative to
   the declared reference tonic and equave;
2. enumerate lattice chord candidates within the configured coordinate/register bounds;
3. match candidate voices injectively to reference targets;
4. compute target-frequency deviation, chord-role mismatch, lattice L1, prime complexity,
   register spread and optional comma-drift costs;
5. retain ordered exact top-K candidates;
6. use the existing exact progression resolver for common tones, crossing, voice leading
   and path selection.

The selected chord remains a ratio/vector/equave-exponent payload. No emitted pitch is
rounded back to 12-TET. Native JI and PIL scores remain parallel evaluations and are not
replaced by reference-target similarity.

### 6.2 Voicing and rhythmic development

Harmony realization selects independently bounded variants for:

```text
voicing: close | open | drop2_like | shell | spread
register: low | mid | high | expanding | contracting
gate: stab | pulse | half_bar | sustained | tied
rhythm: whole | halves | quarters | offbeat | syncopated
voice_count: 2..6, bounded by the resolved chord and instrument polyphony
```

Section functions constrain these choices. Preparation must expose a directional change;
arrival may widen or increase voice count; contrast may use shell/reduced voicing;
closure must reduce activity or sustain a terminal harmony. Repeating the same voicing,
register, gate and rhythm across every section is invalid for a full-song profile.

## 7. Density realization

`density_q` becomes an active control and is no longer metadata-only. Each role owns a
minimum anchor set and a maximum candidate grid. For each bar and role:

```text
target_count = min_count + round_half_even(
  density_q * (max_count - min_count) / 10000
)
```

Candidate events are ordered by:

```text
(structural_priority, SHA256(seed, section, role, bar, candidate_id), candidate_id)
```

Mandatory anchors are retained first; the first remaining candidates fill
`target_count`. `subdivision` is the smallest profile-declared grid able to contain the
selected candidates. Rest probability is derived as:

```text
rest_q = 10000 - density_q
```

but mandatory downbeats, cadence tones and selected transition gestures cannot be removed
by rest selection. Role-specific min/max counts prevent high density from turning a pad
into a drum-like stream or low density from deleting required timing anchors.

## 8. Section role masks

Every section function selects one weighted role mask from a profile-owned closed table.
The initial requirements are:

| Function | Required | Optional |
| --- | --- | --- |
| opening | harmony or texture | drums, bass, melody |
| statement | harmony, foreground | drums, bass, texture |
| preparation | drums, harmony | bass, melody, texture |
| arrival | drums, bass, harmony, foreground | texture |
| contrast | at least one pitched role | drums, bass, texture |
| return | bass, harmony, foreground | drums, texture |
| closure | harmony or foreground | drums, bass, texture |

`foreground` resolves to melody or another profile-declared foreground role. Role-mask
selection precedes density realization. An inactive role emits no ordinary events, but a
transition bundle may schedule a declared pickup, impact, tail or role entry at the
boundary.

## 9. Energy as a composite curve

Each section replaces scalar `[energy_q, energy_q]` behavior with a bounded piecewise-
linear curve. Every control point contains:

```text
position_q
velocity_q
density_q
register_offset_mc
gate_q
timbre_brightness_q
filter_open_q
send_q
stereo_width_q
```

Not every renderer must implement timbre/filter/send controls. The authoritative Program
still records them, and a renderer reports applied and unsupported dimensions. Silent
fallback to velocity-only behavior is forbidden.

Section-function constraints are directional rather than absolute:

- opening establishes or gradually introduces energy;
- preparation has a non-decreasing approach to its boundary unless an explicit dropout
  transition reserves the ending;
- arrival begins at or above the source's final composite energy, except after deliberate
  silence;
- contrast differs in at least two supported dimensions;
- closure is non-increasing in at least two dimensions and ends with reduced density,
  gate, role count or send tail.

## 10. Instrument and WAV architecture

MIDI carries note/control intent but does not supply an audible instrument. The preview
path is therefore:

```text
canonical Project
  -> role-aware MIDI 2.0/MPE or pitch-bend MIDI export
  -> versioned patch assignment
  -> pinned SoundFont/sampler/synth renderer
  -> perceptual preview WAV
```

Three evaluation/reference products remain distinct:

1. `reference.wav`: generated by the existing deterministic Q1.31 renderer, used for
   canonical hashes, cache parity and conformance;
2. `perceptual_preview.wav`: generated by a declared external or enhanced local
   instrument backend, used for human listening and audio-model evaluation.
3. `evaluation_reference.mid`: deterministic SMF type-0 generated from the canonical
   Project, used as an evaluation reference and for audition with external instruments.

The MIDI export uses 480 PPQ, channel 10 for drums, role-specific GM program hints, and
one dynamically allocated channel per simultaneous pitched note. Exact lattice ratios
are converted with `cps-numeric/decimal-log2-rhe-v1`; the nearest MIDI note carries a
per-note pitch bend with a declared ±2-semitone range. The paired
`evaluation_reference_midi.json` binds the algorithm, program map, numeric contract,
pitch-bend range, MIDI SHA-256 and manifest hash. MIDI is an evaluation projection and
does not replace the canonical ratio/vector pitch payload in Project.

### 10.1 Vital preview bundle

The SoundFont stage is optional and is skipped by the Vital backend. The bundle builder
splits Project events into role/lane stems, emits one lower-zone MPE-style MIDI file per
stem, and binds every selected `.vital` preset by SHA-256. Channel 1 is the MPE master;
channels 2..16 are member channels with channel 10 excluded so drum-oriented host
routing cannot be confused with a pitched member channel. Drum lanes are separate Vital
instances and use a fixed trigger note.

The initial Vital assignment covers kick, snare, clap, closed/open hat, fill, bass,
harmony, melody, pad, arp, pluck, vocal chop, counterline, noise riser, impact, and
transition tail. `PI 23` through `PI 27` derive from Vital's embedded White Noise sample
with a filter and bounded amplitude/effect envelope. Kick remains oscillator-based so it
retains a stable low-frequency fundamental.

`vital_render_manifest.json` is non-authoritative. It binds the source Project, MIDI
stem hashes, preset hashes, MPE configuration, host/plugin identities, sample rate, and
channel layout. Until REAPER has rendered and reported every stem and the master,
`status` remains `render_pending`; `reference.wav` is never substituted as a successful
Vital preview.

The preview manifest must bind:

```text
renderer implementation and version
renderer dependency/lock digest
patch or SoundFont asset hashes and licenses
role -> bank/program/patch mapping
drum note map
MPE/pitch-bend range and channel allocation
sample rate, bit depth and channel count
effect chain and numeric parameters
Project hash and exported MIDI hash
```

The initial role intent separates bass, harmony, melody, texture and every drum lane.
Using one patch for all pitched roles or one impulse for all drum lanes is invalid for a
perceptual full-song preview profile.

Because ordinary MIDI note numbers cannot represent arbitrary JI ratios exactly, the
exporter must use MPE/per-note pitch, independent pitch-bend channels or another explicitly
versioned microtonal protocol. If the selected renderer cannot realize the required pitch
resolution or polyphony, preview rendering fails; it must not silently quantize to 12-TET.

## 11. Diversity requirements

A full-song realization profile must provide:

- at least eight motif templates and four contour families per 24-seed cohort;
- at least two drum-pattern families for every section function;
- at least two bass patterns for every section function;
- at least eight functional harmony templates across the profile;
- at least three harmony voicing variants and three rhythm/gate variants;
- at least two eligible role masks for every function except an intentionally fixed
  arrival policy;
- at least two energy-curve shapes for preparation, arrival, contrast and closure.

These are profile-capacity requirements. Cohort reports separately measure actual
exposure; passing schema validation does not prove adequate sampled diversity.

## 12. Failure codes

```text
COMPOSITION_REALIZATION_PROFILE_INVALID
COMPOSITION_ROLE_MASK_UNAVAILABLE
COMPOSITION_DENSITY_REALIZATION_UNAVAILABLE
COMPOSITION_DRUM_PATTERN_UNAVAILABLE
COMPOSITION_BASS_COUPLING_UNAVAILABLE
COMPOSITION_REFERENCE_HARMONY_UNAVAILABLE
COMPOSITION_LATTICE_HARMONY_UNAVAILABLE
COMPOSITION_MELODY_RELATION_UNAVAILABLE
COMPOSITION_ENERGY_CURVE_UNAVAILABLE
COMPOSITION_PREVIEW_INSTRUMENT_UNAVAILABLE
COMPOSITION_MICROTONAL_EXPORT_UNAVAILABLE
COMPOSITION_PREVIEW_RENDER_FAILED
```

Validation proceeds in processing-order sequence. The first failure in playback order
wins. Preview-render failure does not invalidate canonical compilation/reference render,
but the candidate is ineligible for perceptual listening until a preview succeeds.

## 13. Implementation stages

1. Add the closed realization-profile and realization-plan schemas and authoritative
   fixtures.
2. Implement active density and role-mask realization.
3. Implement multi-lane drums and section-conditioned bass.
4. Extend reference-target harmony vocabulary and connect exact lattice progression.
5. Implement motif relations, contour and register arcs.
6. Implement composite energy curves and transition interaction.
7. Extend the deterministic trial catalog to separate all roles and drum lanes.
8. Add the non-authoritative MIDI/MPE preview adapter and pinned instrument backend.
9. Regenerate 4-, 24- and 100-seed cohorts before G1/G2 recalibration.

## 14. Implemented milestone: role masks and active density

The first implementation milestone is available as the closed profile
`composition_realization_v2_1.json`. When explicitly supplied to lowering, it:

- selects a deterministic weighted role mask for every section;
- converts `density_q` into bounded drum, bass and harmony event counts;
- preserves mandatory timing anchors;
- thins melody interiors while preserving the first identity event and final cadence event;
- creates section-specific harmony rhythm material so harmony density is audible;
- clips melody gates at the next active harmony occurrence to preserve chord binding.
- compresses structural `energy_q` to
  `audible_velocity_q = 8500 + round(energy_q * 1500 / 10000)` for event accents and
  realization velocity. Thus the full structural range changes direct amplitude only
  within `8500..10000`; large-scale contrast remains primarily arrangement and density.
- realizes the canonical `texture` track as one of eight deterministic functional
  subroles: `pad`, `noise_riser`, `fx_impact`, `transition_tail`, `arp`, `pluck`,
  `vocal_chop`, or `counterline`. These names are material-level roles, so existing
  Program, Project, evaluation, cache, and oracle role enumerations remain compatible.
- conditions texture subroles on section function: opening favors pad/pluck,
  preparation favors riser/arp, arrival favors impact/chop/arp, and closure favors a
  transition tail.

The legacy two-argument lowering call retains 2.0 behavior. The song-generation CLI now
supplies the 2.1 realization profile by default and binds its hash in
`cps.composition-song-generation-receipt` version `1.1.0`.

Section-specific bass-pattern vocabulary, expanded harmony templates, new melody
relation types, complete composite energy curves and the instrumented preview backend
remain later milestones. Multi-lane drums and the functional texture subroles are now
implemented in the deterministic reference path.
