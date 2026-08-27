# MIDI Creator Toolkit

`/midi-toolkit` is the shared performance-capture entry point for the
composition workbenches. It converts a physical or on-screen keyboard
performance into both a full exact-ratio note sequence and a bounded motif.

## Input And Capture

- Web MIDI input selection and channel filtering use the browser Web MIDI API.
- Note on/off velocity and channel are retained. CC64 sustain delays note-off
  until pedal release.
- Audio thru is optional. Its default **Selected exact-ratio scale** mode maps
  every incoming key to the nearest tone in the active scale before sounding;
  12-tone equal temperament remains available for comparison. A ten-note
  screen keyboard and `A S D F G H J K L ;` keys use the same path.
- Recording uses the selected tempo, optional one- or two-bar count-in, and
  optional overdub. Project JSON stores beat positions rather than device
  timestamps.

Web MIDI permission is browser-controlled and normally requires a secure
context. `http://localhost` and `http://127.0.0.1` are treated as secure local
origins by supported browsers; access through an untrusted LAN origin may not
expose MIDI devices.

## Scale Assignment

The Scale library unifies palettes already used by Fractional Pop, Fractional
J-Pop, Kawaii Fractional Future Pop, harmonic/subharmonic series, and the
Bohlen-Pierce workbench. A scale saved in the main Workbench appears under
**Saved in Workbench** after **Refresh**. The embedded **Generate prime-lattice
scale** control uses the same `Prime basis`, `Exponent limit`, `Weighted
height`, `Cluster tolerance`, and `Target notes` search parameters as
Prime-Limit Harmonic Explorer, then assigns its octave-reduced representative
ratios immediately.

The ratio textarea remains editable and switches the source to **Custom
ratios**. `Root MIDI` identifies the controller key for `1/1`; `Base Hz` is the
frequency sounded by that key. `Equave` is `2/1` for octave scales and `3/1`
for Bohlen-Pierce. The live monitor shows both the physical key name and the
selected ratio. Changing a scale reprocesses any captured take immediately.

MIDI input uses a white-key scale layout. `Root MIDI` must be a white key; each
successive white key is the next degree in the active scale, independently of
the scale's note count. After the final degree it continues into the next
equave. Black keys do not sound or enter a recording.

## Live Pitch Circle

The MIDI input view plots every currently held or sustain-held monitor voice
on a continuous Pitch Circle. Cyan outer-ring markers are the frequencies
actually sounding; marker size follows velocity and labels show the assigned
ratio. Each sounding tone also produces a magenta inner-ring guide at `3f`,
with a dashed line connecting the fundamental and its third harmonic.
Simultaneous fundamentals and their harmonic guides form separate polygons.
The segmented control changes only the visualization period:

- **Octave 2/1** wraps the actual sounding frequency over 1200 cents and shows
  twelve reference divisions.
- **Tritave 3/1** wraps the same frequency over `1200 log2(3)` cents and shows
  thirteen 13-EDT reference divisions. Because `3f` is one tritave above the
  source, its guide returns to the same angle and remains visible on the inner
  ring.

The circle follows both exact-ratio and 12-TET Monitor tuning. Switching the
circle period does not retune or restart sounding voices.

Bohlen-Pierce capture, playback, Project JSON, and MPE MIDI are supported.
Motif Development and Vital Pack handoff remain disabled for a `3/1` equave,
because those composers currently use an octave-based pitch contract.

## Performance Processing

`POST /api/midi-toolkit/process` performs the reusable server-side work:

1. optionally removes leading silence;
2. applies grid quantization with continuous strength and swing;
3. groups near-simultaneous notes by quantization slot;
4. limits each stack to one through four voices, preferring higher velocity;
5. maps consecutive white keys to consecutive supplied fractional-ratio scale degrees
   across the selected equave;
6. derives a duration-weighted anchor chord and the scale's odd-prime basis;
7. reports range, density, velocity, polyphony, syncopation, contour, chord
   affinity, rests, and any discarded voices.

The complete mapped performance remains available for audition and MPE MIDI.
Motif Development accepts at most 32 steps, so longer performances expose the
first 32 slots as `motif.notes` and retain all mapped notes in `midi_notes`.

## Editing And Output

The Performance Roll overlays captured MIDI positions and mapped motif notes.
The page provides semitone/octave transpose, temporal reversal, velocity
normalization, equal-tempered captured playback, and exact-ratio motif
playback. Project JSON is lossless for the processed workflow. MPE MIDI uses
the existing pitch-bend exporter and the selected `1/1` base frequency.

## Handoffs

- **Send to Motif Development** transfers the derived anchor chord, prime
  basis, stack-aware notes, rhythm signature, and evaluation summary through
  session storage. The received motif replaces initial random generation and
  can immediately be auditioned or expanded with Development Tree.
- **Send theme to Vital Pack** creates a single `theme` node using the same
  motif and existing version-3 Vital transfer contract. Vital Pack can then
  arrange it across a complete song.

Scale ID, display name, ratios, and equave are stored in Project JSON; browser
MIDI device identity and permission are not stored.
Future work includes MIDI clock synchronization, multi-take comping, per-note
editing, MIDI file import, and MPE controller-dimension capture.
