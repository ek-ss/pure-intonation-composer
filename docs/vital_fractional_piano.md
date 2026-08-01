# PI22 Fractional Piano

## Status

Implemented Vital 1.6-compatible synthetic piano preset:

- preset: `backend/app/static/vital_presets/PI 22 Fractional Piano.vital`
- archive: `backend/app/static/vital_presets/PI Fractional Piano.zip`
- reproducible builder: `backend/tools/build_vital_fractional_piano.py`

## Sound Design

PI22 is a piano-like synthetic key sound rather than a multisampled acoustic
piano. It derives from PI13 Fifth Keys and keeps oscillator random phase and
unison detune disabled so independent per-note pitch bends remain clear.

The main oscillator supplies the body. A quiet second oscillator one exact
octave above adds a hammer-like upper partial without changing the pitch
class. The amplitude envelope uses a 2 ms attack, long decay, low sustain, and
an 820 ms release. Filter key tracking and velocity tracking make low notes
darker and harder strikes brighter. Chorus and delay are disabled; only a
small room reverb and light compression remain.

## Integration

Vital Pack Composer now uses PI22 for both ordinary exact-ratio scale runs and
transferred-motif piano material. The Instrument Roles area provides both the
individual `.vital` file and piano archive downloads. Project JSON, tuning
timelines, REAPER manifests, and pitch-bend MIDI identify this part as `PI22`.
The instrument-profile response is version `0.2`. The MIDI endpoint continues
to accept legacy project events whose instrument ID is `PIANO`.

Composition Explorer exposes PI22 with these constraints:

- roles: keys, harmony, arpeggio;
- recommended range: MIDI 48-96;
- generated maximum: eight simultaneous voices;
- section affinity: Intro, Verse/A/B, Chorus, Instrumental, and Final;
- tuning policy: per-note exact.

PI22 is included in the default Fractional Pop and Fractional J-Pop explorer
palettes. It remains optional in Kawaii Fractional Future Pop.

## DAW Use

1. Download and load `PI 22 Fractional Piano.vital` in Vital.
2. Import the generated MPE/pitch-bend MIDI on the PI22 track.
3. Match Vital and the DAW pitch-bend range to the export setting.
4. Keep simultaneous notes on independent MIDI channels when their exact
   fractional ratios require different bends.

The Web Audio preview approximates the envelope and pitch, but the `.vital`
preset is the authoritative sound design.
