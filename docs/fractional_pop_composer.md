# Fractional Pop Composer

**Status:** Experimental implementation
**Page:** `/fractional-pop-composer`

Fractional Pop Composer is a pop-focused variation of Vital Pack Composer.
It turns an exact fractional-ratio scale into a complete sectional song with
harmony, bass, hook melody, drums, and background texture. The page uses the
implemented Genre Arrangement Pipeline with the `pop` profile, then presents
the result through Vital-oriented part names and export controls.

## Workflow

1. Select Bright 5-limit, Minor 5-limit, 7-limit color, or enter a custom
   comma-separated ratio scale.
2. Choose the base frequency, tempo, length, Pop color, and keyboard
   performance pattern.
3. Shape energy, density, syncopation, harmonic color, repetition, and section
   contrast, then generate the song.
4. Inspect the form, exact-ratio pitch circle, chord progression, and arranged
   Vital roles. Selecting a progression row auditions that chord and marks its
   tones on the circle.
5. Audition the canonical event timeline or export MPE-style pitch-bend MIDI,
   a WAV preview, or Project JSON.

## Exact-Ratio Contract

The scale accepts positive integer fractions such as `1/1`, `8/7`, and
`7/4`. At least five tones are required. The composer automatically creates
root-specific degree-template chords. Bright color uses triads, Bittersweet
adds seventh color to ii and vi when the scale permits it, and Open uses
suspended shapes. Distinct root-specific candidates let the arranger form
functional I/IV/V/vi, I/ii/IV/vi, or I/IV/V motion instead of alternating
multiple chord shapes over one stationary root.

Chord tones, bass notes, hook notes, and texture notes are selected from that
scale. Register placement may multiply or divide a ratio by powers of two,
but its octave-reduced pitch class remains a member of the selected ratio
scale. Ratios stay exact strings in the project until Web Audio playback,
MIDI pitch-bend encoding, or WAV rendering.

## Pop Controls

| Control | Effect |
| --- | --- |
| Pop color | Selects bright, bittersweet, or open root-degree vocabulary |
| Keys performance | Uses automatic, block, arpeggio, or stride realization |
| Energy | Raises section intensity and velocity |
| Density | Changes note and drum activity |
| Syncopation | Moves rhythmic emphasis away from strong beats |
| Harmonic color | Increases use of suspended and seventh material |
| Repetition | Controls recurring hooks and patterns |
| Root movement | Discourages reuse of roots heard in the previous three chords |
| Section contrast | Separates verse, chorus, bridge, and outro intensity |

The melody and drum parts can be disabled independently. A seed reproduces
the same project; **New seed and generate** explores another deterministic
variation.

## Vital Role Mapping

| Arrangement role | Displayed instrument |
| --- | --- |
| Harmony | PI02 Dream Chord |
| Texture | PI03 Air Pad |
| Melody | PI04 Gentle Pluck |
| Bass | PI05 Warm Bass |
| Kick | PI09 Pop Kick |
| Snare | PI10 Pop Snare |
| Closed hat | PI11 Pop Closed Hat |
| Percussion | PI12 Pop Perc |

The four drum cards provide the corresponding `.vital` preset downloads.
Exported MIDI and Project JSON use separate PI09-PI12 tracks while retaining
the standard drum trigger notes. Browser playback and WAV use the arranger's
built-in preview synthesis; the page does not instantiate the Vital plug-in
or automate a DAW. See [vital_pop_drums.md](vital_pop_drums.md).

## Integration Boundary

The page is a specialized client of `POST /api/arrange/generate`,
`POST /api/arrange/midi`, and `POST /api/arrange/render`. Its Project JSON is
the canonical ArrangementProject 1.1 document and can be sent back to the
MIDI or render endpoints without regenerating the composition.
