# Fractional J-Pop Composer

`/jpop-composer` generates a seeded J-Pop arrangement with the familiar
intro, A-melody, B-melody, chorus, bridge, final-chorus, and outro form. The
page keeps exact fractional ratios in every pitched event and exports the same
timeline as Project JSON or pitch-bend MIDI.

## Section Harmony

| Section | Harmonic rule | Exact construction |
| --- | --- | --- |
| A-melody | pure-fifth lattice | Roots and chord tones are octave reductions of powers of 3; the first chord interval is always `3/2`. |
| B-melody | pure minor third | Every chord contains the root-relative interval `6/5`, plus `3/2`. |
| Chorus | 13-limit fifth shift | Roots move on the `(a,c)` lattice `3^a * 13^c`; each chord retains a root-relative `3/2` and adds `13/8` color. |

`13-limit shift depth` multiplies the chorus exponent on the 13 axis. A depth
of 2 therefore visits `13^2` lattice positions while octave reduction keeps
playback in a practical register. The Harmonic Plan table shows the exact
root, tones, and `(3,5,13)` exponent vector for every bar. Clicking a row
auditions that chord.

## Form And Parts

One to three A/B/chorus cycles may be selected. The fixed framing sections
produce 40, 60, or 80 bars in total.

| ID | Role | Tuning |
| --- | --- | --- |
| PI04 | instrumental hook | per-note exact ratio |
| PI05 | bass root | per-note exact ratio |
| PI09-PI12 | kick, snare, closed hat, percussion | fixed GM drum notes |
| PI13 | A-melody fifth keys | per-note exact ratio |
| PI14 | B-melody minor-third pluck | per-note exact ratio |
| PI15 | 13-limit chorus lead | per-note exact ratio |
| PI16 | vocal guide | per-note exact ratio, monophonic intent |

The vocal lane generates section-aware phrases, intentional rest bars,
cadences, and guide syllables. It is a MIDI/Vital melody guide, not recorded
or synthesized human singing. In a DAW, route PI16 MIDI to a vocal synth or
replace it with a recorded performance.

## Vital Instruments

`J-Pop Vital pack` downloads PI13-PI16 as a ZIP. Individual download links
are also shown for PI09-PI16. PI13-PI16 are derived reproducibly from the core
Vital pack and tailored to their roles: clear fifth keys, a shorter
minor-third pluck, a wider chorus lead, and a restrained monophonic vocal
guide. The separate `Vital drum pack` contains PI09-PI12.

Load a `.vital` preset in Vital, set the MIDI track pitch-bend range to the
same value used by the export workflow, and keep each simultaneous pitched
voice on a separate MIDI channel when exact independent bends are required.

## Workflow

1. Choose tempo, form cycles, vocal activity, and chorus shift depth.
2. Generate with a fixed seed, or use `New seed and generate` for a variation.
3. Inspect the form, exact harmony table, vocal roll, and event counts.
4. Use `Play excerpt` for an eight-bar browser audition.
5. Export `MPE MIDI` and `Project JSON`, then load the included Vital presets
   on the corresponding tracks.

The JSON is the authoritative interchange format: it preserves section
roles, exact ratios, lattice vectors, guide syllables, tuning metadata, and
the deterministic seed.
