# Capability, 3/1 Export, and Compatibility Contract

**Status:** normative capability boundary

## 1. Preflight

Every compiler, renderer, exporter, projector, evaluator, and mutation engine
publishes a content-addressed CapabilityManifest. Before work or output-file
creation, preflight compares operation, input schema/version, equave, generator
dimension, event/polyphony limits, required provenance variants, instrument
engines, and requested format options. Success returns a capability receipt;
failure returns one stable code and creates no partial artifact.

Unknown capability is unsupported. There is no fallback equave, octave folding,
12-TET snapping, instrument substitution, schema downgrade, or option removal.

## 2. Native equave policy

SongProgram exact arithmetic, GEN0-A/B search, Project 1.2 validation, symbolic
evaluation, Scala tuning export, and the GEN0-C reference renderer support both
`2/1` and `3/1` through the same generic rational path. A capability declaring
either equave must pass its corresponding Conformance Pack fixtures.

An exporter may support a strict subset. The initial Project 1.1 compatibility
projector supports only `2/1`; `3/1` returns
`UNSUPPORTED_EQUAVE_CAPABILITY`. This is not a blocker for native 3/1 Project,
reference WAV, Scala, or symbolic evaluation.

## 3. MIDI derived export

Microtonal MIDI is explicitly approximate and never authoritative. The v1
format is SMF type 1 with MPE-style one active pitched note per member channel,
channel 10 reserved for drums, pitch-bend sensitivity RPN emitted before notes,
and deterministic channel allocation by `(start_tick,event_id)`.

For each exact event frequency, choose MIDI note `0..127` minimizing absolute
millicent bend; ties choose the smaller note. Pitch bend uses a declared
integer range of 1..48 semitones and 14-bit value
`RHE(8192 + bend_mc * 8192 / (range_semitones*100000))`, clamped only after
preflight proves the exact bend lies in range. Reconstructed-frequency error is
reported per event and must be <=1000 millicents (1 cent) for capability
success. Channel exhaustion, bend-range failure, or tolerance failure aborts
without MIDI bytes.

Note-off precedes note-on at the same tick; remaining events sort by canonical
Project event order. Tempo/meta events occupy track 0; each Project track has a
stable SMF track. Running status is disabled, text metadata is ASCII frozen,
and serialization has no timestamps.

This policy works identically for 2/1 and 3/1 when range/polyphony/tolerance
preflight passes. Exporter support is therefore declared by tested capability,
not by assuming an octave-equivalent source space.

## 4. Scala export

Scala export writes the sorted unique exact classes actually referenced by the
Project, reduced into `[1,equave)`, followed by the equave as period. Ordering
is `(NumericContract phase_mc,numerator,denominator)`. Ratio text is exact;
description is ASCII and timestamp-free. Empty pitched Projects reject.
Keyboard mapping is a separate optional artifact and must declare reference
frequency/key; absence never invents 12-TET placement.

## 5. Project 1.2 to 1.1 projection

Projection is a pure, versioned, lossy adapter. Its envelope stores source
artifact hash, projector build/manifest hashes, output hash, and a sorted loss
manifest of `{source_pointer,loss_code,legacy_encoding}`.

Required losses include provenance union, material instances, ResolvedChord
cores/occurrences, nullable chord index sentinel, generic domain/equave data,
and fields unavailable in 1.1. Projection succeeds only when every loss has a
registered deterministic encoding and the target exporter accepts the result.
Unregistered loss is `UNREPRESENTABLE_PROJECT_FIELD`.

## 6. Legacy 1.1 isolation

Loading 1.1 produces `LegacyProjectEnvelope` with
`provenance_status=legacy_unverified`; it never produces native 1.2. Playback,
render regression, MIDI export, and baseline fingerprints may accept it only
when their manifest explicitly declares legacy input. SongProgram
reconstruction, mutation, lineage, native pitch metrics, calibration truth,
and QD insertion return `PROVENANCE_REQUIRED`.

Roundtrip guarantees only canonical clock/track/form/event cores from
1.1→Legacy→1.1. No inferred vector, material, chord, semantic address, or
equave is authoritative.

## 7. Capability receipt and errors

The receipt records input artifact hash, capability manifest hash, operation,
matched rule ID, options hash, success/error, and output hash when successful.
Stable errors include:

- `UNSUPPORTED_SCHEMA_CAPABILITY`
- `UNSUPPORTED_EQUAVE_CAPABILITY`
- `UNSUPPORTED_PROVENANCE_CAPABILITY`
- `UNSUPPORTED_INSTRUMENT_ENGINE`
- `EXPORT_POLYPHONY_EXCEEDED`
- `MIDI_BEND_RANGE_EXCEEDED`
- `MIDI_TUNING_ERROR_EXCEEDED`
- `UNREPRESENTABLE_PROJECT_FIELD`
- `PROVENANCE_REQUIRED`

## 8. Acceptance

- every public operation runs preflight and leaves no file on failure;
- 2/1 and 3/1 reference WAV/Scala fixtures succeed byte-identically;
- MIDI boundary fixtures cover note 0/127, bend center/extremes, 1-cent
  inclusive tolerance, simultaneous channel capacity, and note-off ordering;
- 3/1 projector rejection is stable and cannot be bypassed by ratio folding;
- projection loss manifest is complete under field-mutation property tests;
- no Legacy envelope enters native mutation, calibration, or QD APIs.
