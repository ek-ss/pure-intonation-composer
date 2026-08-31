# GEN0-C Reference Renderer and Evaluation Contract

**Status:** normative and implementation-ready deterministic baseline

## 1. Purpose

GEN0-C supplies reproducible previews for technical validation and listening
calibration. It is not the final production mix. MIDI, DAW, third-party plugin,
GPU, and operating-system audio paths are non-authoritative.

## 2. Frozen render format

- input: canonical native ArrangementProject 1.2;
- output: RIFF/WAVE, signed little-endian stereo PCM32, 48,000 Hz;
- internal sample: signed Q1.31; multiply uses signed 64-bit intermediate and
  round-half-to-even back to Q1.31;
- processing block: 256 frames; block boundaries cannot alter state or output;
- event time: `RHE(tick * 60 * 48000 * 1000 /
  (tempo_milli_bpm * ticks_per_beat))`, independently for start and end;
- track processing and final summation: track-ID byte order, then channel left
  before right, signed checked 64-bit accumulator;
- final conversion: saturate once to int32; no limiter, normalization, dither,
  noise shaping, hidden headroom, or fallback effects;
- render length: maximum actual pitched release end or drum one-shot end, then
  exactly 256 zero frames; WAV metadata contains only frozen format fields.

Any overflow before final saturation is `RENDER_ACCUMULATOR_OVERFLOW`. Missing,
modified, unsupported, or out-of-range catalog data is a typed failure and
never selects a substitute instrument.

## 3. GEN0 reference instrument engine

GEN0 supports only `sample-linear-q31/v1`. Catalog schema, canonical bytes,
digest, content-addressed asset resolution, canonical PCM32 WAV, pitched/drum
unions, release, and failures are governed by
[instrument_catalog_render_manifest_contract.md](instrument_catalog_render_manifest_contract.md).

For pitched playback:

```text
playback_rate = project_base_millihz * exact_event_ratio / asset_root_millihz
phase_increment_q32 = RHE(playback_rate * asset_sample_rate * 2^32 / 48000)
```

Phase starts at zero. Linear interpolation uses the upper 32 phase bits as
index and lower 32 as fraction, with one Q1.31 half-even multiply per endpoint.
No band-limited resampling is implied. `loop_mode=none` emits zero after the
asset; `forward` wraps over `[loop_start,loop_end)` with checked integer phase.

Velocity gain is `velocity/127`; track gain is `gain_q/10000`. Pan is linear:
`left_q=max(0,10000-max(pan_q,0))`,
`right_q=max(0,10000+min(pan_q,0))`. Apply velocity, catalog, track, then pan in
that order, rounding after every multiply. Note release uses the catalog
contract's exact `release_frames` ramp; drums resolve by
`(track.instrument_id,event.drum_note)`, ignore Project ratio/duration, and play one-shot.
Voice stealing is forbidden: exceeding polyphony fails before rendering.

## 4. Render identity and parity

`render_manifest_digest` and its exact preimage are governed by the catalog and
manifest contract. `render_hash` hashes the complete WAV bytes. The
Compile/Evaluation report stores Project artifact hash, manifest digest, WAV
hash, PCM payload hash, frame count, saturation count, peak absolute sample,
and per-track hashes.

The reference implementation must be bit-identical across the Conformance Pack
process matrix. A faster renderer is acceptable only by full PCM hash equality.
No tolerance comparison may be called the reference result.

## 5. Symbolic PitchAuditReport v1

Pitch audit operates on Project events, not audio. Exact class is exact ratio
reduced into `[1,equave)`. Phase uses NumericContract integer millicents modulo
the equave period. Simultaneous duplicate events with the same track, start,
end, ratio, and source semantic address are counted once.

Near-class clustering `complete-link-circular-v1` is deterministic:

1. sort exact classes by `(phase_mc, ratio_n, ratio_d)`;
2. try every circular cut immediately before a class;
3. greedily append to the current cluster only when circular diameter of all
   members remains `<=near_class_merge_millicents`;
4. choose the partition minimizing `(cluster_count, sorted cluster diameters,
   cut_index, canonical member lists)`.

Metrics use integer event weight
`duration_ticks * velocity * track_gain_q`; zero-weight events are excluded.
`audible_color_event_share_q` is the half-even ratio of weight whose nearest
reference-grid distance lies in the declared inclusive band. Entropy uses only
a separately versioned fixed-point log2 table; until that table and its golden
dataset exist, entropy is nullable and audit-only. Coordinate inflation,
exposed-section count, recurrent relation count, and exact/near class counts
remain audit columns, never chord or Project validity inputs.

## 6. Calibration artifacts, not silent specification changes

Renderer ceiling audio, licensed genre references, listener cohort, randomization
schedule, responses, exclusion rules, confidence intervals, and chosen gates
form a content-addressed `CalibrationDataset`. A `CalibrationDecision` names
that dataset and promotes specific audit metrics/thresholds. Before promotion,
no perceptual metric may reject a candidate or affect QD quality.

Listening tasks report separately: technical listenability, genre fit,
preference, tuning perceptibility, and tuning appropriateness. They use blinded
random order and include 12-TET matched-render, same-lattice alternate-spelling,
and deliberately excessive-microtonality controls.

## 7. Acceptance

- 100 renders and the cross-process matrix have identical WAV/track hashes;
- one asset byte changes catalog and render-manifest identity;
- block sizes 64/256/1024 in a test-only implementation yield identical PCM;
- onset/end rounding, loop wrap, interpolation half-ties, saturation, pan,
  release, silence, and polyphony boundaries have goldens;
- 2/1 and 3/1 pitch fixtures produce the expected phase increment and audible
  frequency in a zero-crossing audit;
- near-cluster results are invariant to event/class order and circular cut;
- audit values cannot change Project hash, validity, or GEN0-B selection.
