# Kawaii Fractional Future Pop

`/kawaii-future-pop` combines kawaii future bass, pop song form, minimal
phase processes, exact fractional-ratio scales, and a vocal guide in one
deterministic composition surface.

## Musical Structure

The one-cycle form is 44 bars:

`Intro 4 -> Verse 8 -> Pre 4 -> Drop 8 -> Minimal Break 8 -> Final Drop 8 -> Outro 4`

Selecting two cycles inserts another Verse, Pre, and Drop before the Minimal
Break. Verse harmony follows an exact-ratio pop root path analogous to
`I-V-vi-IV`. Pre sections rise into the drop. Drop chords use four scale
degrees, syncopated chord stacks, half-time drums, sparkle accents, and an
explicit sidechain envelope. Each Drop enters with a consonant three-voice
stack, moves through an open three-voice stack, adds a gentle fourth voice,
and reserves the 13-limit color stack for its final two bars. Voice count only
changes by one at a stage boundary. The break reduces the material to two
roots and a three-tone cell.

## Fractional Scale

Three palettes are supplied:

| Palette | Character |
| --- | --- |
| 13-limit sparkle | 5/7-limit pop material plus `13/8` color |
| 7-limit pastel | softer 5/7-limit scale without the 13-prime color |
| 3 x 7 x 13 lattice | ratios such as `7/6`, `39/32`, `21/16`, and `13/8` |

The scale textarea is editable. It requires 7-12 unique positive ratios and
must contain `1/1`. Every pitched event, including bass, vocals, chords,
sparkles, and minimal pulses, is created from a scale degree. Register changes
use powers of two, so octave reduction always returns to the selected palette.

## Minimal Process

`Minimalism` changes how long the harmonic root is held and how sparse the
repeated pulse cell becomes. The A and B pulse lanes use the same exact-ratio
cell. `Phase shift` offsets lane B by 0, 1/4, 1/2, or 3/4 beat. The JSON export
preserves each cell, lane, pulse count, and phase offset.

## Vocal Part

The vocal generator has three policies:

| Style | Behavior |
| --- | --- |
| Hooky | repeated drop hook with more spacious verse phrasing |
| Airy | fewer, longer notes and more space |
| Chopped | eighth-note drop chops with short gates |

`Vocal activity` controls phrase-level rests. Intro, Minimal Break, and Outro
remain available as intentional vocal-negative space. PI19 events include
exact ratios, guide syllables, phrase IDs, and `vocal_syllable` or
`vocal_chop` articulation. This is a melodic production guide, not synthesized
human singing; route it to a vocal synth or replace it with a singer in a DAW.

## Vital Pack

The `Kawaii Vital pack` ZIP contains:

| ID | Preset | Role |
| --- | --- | --- |
| PI17 | Candy Pluck | Verse and Pre harmony |
| PI18 | Future Chord Stack | sidechained Drop harmony |
| PI19 | Fractional Vocal Guide | vocal melody and chops |
| PI20 | Minimal Pulse | phase-shift cells |
| PI21 | Sparkle Bell | high Drop color accents |

PI05 supplies bass and PI09-PI12 supply the separate drum kit. PI17-PI21 keep
random oscillator phase and internal pitch modulation disabled so exported
per-note pitch bends remain clear. PI18 is intentionally compact; apply the
exported sidechain envelope or a DAW compressor after loading the preset.

## Workflow

1. Select or edit a ratio palette.
2. Set Minimalism, Drop intensity, vocal policy, and phase shift.
3. Generate with a fixed seed or request a new seed.
4. Inspect the form, Pitch Circle, harmony table, and vocal/minimal roll.
5. Audition the first Drop, then export Project JSON and MPE-oriented MIDI.
6. Load the matching Vital preset on each track and configure the DAW pitch
   bend range consistently with the MIDI import.

The JSON is authoritative for exact ratios, section intent, minimal-process
metadata, sidechain triggers, vocal syllables, and reproducibility.
