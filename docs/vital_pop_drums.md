# Vital Pop Drums

**Status:** Experimental implementation
**Preset directory:** `backend/app/static/vital_presets/`

The former External Pop Kit is implemented as four self-contained Vital 1.6
presets. Each drum occupies its own DAW track so its envelope, level, effects,
and processing can be edited independently.

| ID | Preset | Layer | Trigger |
| --- | --- | --- | --- |
| PI09 | PI 09 Pop Kick.vital | Synthesized low kick | MIDI 36 |
| PI10 | PI 10 Pop Snare.vital | Oscillator plus embedded-noise snare | MIDI 38 |
| PI11 | PI 11 Pop Closed Hat.vital | Short embedded-noise hat | MIDI 42 |
| PI12 | PI 12 Pop Perc.vital | Short tonal percussion | MIDI 39 |

## Use

1. Download the complete drum-pack ZIP or individual `.vital` files from the
   Vital Roles section of Fractional Pop Composer and import them into Vital.
2. Export the composition MIDI and place PI09, PI10, PI11, and PI12 on the
   correspondingly named MIDI tracks.
3. Keep the trigger notes unchanged. Drum events do not use pure-intonation
   retuning and declare `fixed_drum_note` as their tuning policy.

The normal Vital Pack API and REAPER manifest use the same four IDs. Legacy
`DRUMS` events remain accepted by the MIDI endpoint for imported projects, but
newly generated projects emit PI09-PI12.

## Sound Design

- PI09 uses a mono low oscillator, a short decay, light drive, and compression.
- PI10 combines a tonal body with the template's embedded white-noise sample.
- PI11 uses the embedded noise source with a very short envelope and bright
  filtering.
- PI12 uses the Glass Bell oscillator structure with a shortened envelope and
  restrained reverb.

All four presets disable unison detune and time-based modulation so transient
timing stays precise. `backend/tools/build_vital_pop_drums.py` deterministically
rebuilds them from the original PI05 and PI06 Vital Pack presets.
