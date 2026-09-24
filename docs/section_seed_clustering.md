# Section exploration: 1,000-seed prescreen and symbolic compile cost

## Measured result (current local machine)

- Before exact candidate pruning, `section_variation.json` /
  `section_variation_roles.json`, seed 1, `generate_composition_song.py --skip-wav`
  **did not finish in 300 seconds**. After exact candidate pruning and
  continuous chord coverage, the same seed compiled in **21.27 seconds**.
- The same profile's `generate_composition_plan` for seeds 0–999: **10.91 s**;
  plan feature extraction, 16-medoid clustering and report write included:
  **11.22 s**. These are plan-stage measurements, not WAV-skip song timings.

The default full-song manifest includes 4-voice 12/19-EDO and JI references.
Seed 1 selects a 4-voice `3/1`, 19-division reference. The exact GEN0-A resolver
enumerates permutations of candidate lattice pitches per anchor; its configured
domain has thousands of admissible placed pitches. Even a tighter 24-bit
reduced-ratio cutoff leaves ~5,525 placements in the `3/1` domain, or
~168 billion tail assignments for a 4-voice query **per distinct anchor/intent**
before the later eligibility filters. The actual compiler permits a wider
bit cutoff. The exact solver now prunes impossible partial assignments while
retaining exact top-K ordering and the original `examined_assignments` count.

The 1,000-seed WAV-skip cohort with 8 workers took **2,475.73 s (41m16s)**:
292 Project-complete songs and 708 generation failures. Failures were
`PROGRESSION_NO_PATH` (689), `COMPOSITION_LOWERING_LIMIT_EXCEEDED` (11), and
`MIDI_NOTE_OUT_OF_RANGE` (8). Of 292 compiled songs, 47 failed the symbolic
recall check; 245 passed every check available without PCM. They remain
`incomplete` for archive admission until audio checks run.
The 292 successful Projects include 172 three-voice and 120 four-voice
reference selections, 21 JI-reference selections, both equaves, both form
families, and all 16 opening/closure combinations. This is coverage among
successes, not evidence that the 708 failures have the same distribution.

```sh
backend/.venv/bin/python backend/tools/run_composition_generation_cohort.py \
  --seeds 1000 --workers 8 --piano-style none --skip-wav \
  --profile backend/songprogram_conformance/profiles/g1_experiments/section_variation.json \
  --realization-profile backend/songprogram_conformance/profiles/g1_experiments/section_variation_roles.json \
  --output local_authority/section_variation_symbolic_1000
```

The command exits nonzero on any failed seed but retains successes and a
`cohort_report.json` with a reason for every attempted seed.

## Completed plan-only exploration

```sh
backend/.venv/bin/python backend/tools/cluster_section_seed_plans.py \
  --profile backend/songprogram_conformance/profiles/g1_experiments/section_variation.json \
  --seeds 1000 --clusters 16 \
  --output local_authority/section_variation_1000_plan_clusters.json
```

Report `sha256:ef6d18acdc81ff900da9620315ca6089062e765a816ddd14b8b9ae18360ee229`
contains all 1,000 plan hashes, features and cluster assignments. Selected seeds:

```text
56 92 218 228 266 543 554 607 771 805 864 867 888 933 934 963
```

All four opening types, all four closure types and both form skeletons occur
among these representatives. Cluster sizes are 28–106. Selection uses
deterministic farthest-first initialization followed by within-cluster medoids.
This is a **non-authoritative structural prescreen**, not a perceptual
similarity estimate.

### Feature choice

| Feature | Source | Why it helps |
| --- | --- | --- |
| Opening/closure bars, energy, density, foreground | plan | Different entrances, exits and foreground behavior |
| Ordered section functions | plan | Distinguishes full form skeletons |
| Per-function bars, energy, density, occurrence count | plan | Separates intermediate section pacing and arc |
| Harmonic-function occupancy | plan | Distinguishes planned trajectory rather than only root names |
| Motif-operation occupancy | plan | Separates rest, statement, recall, answer, development |

Opening/closure and form get higher distance weights than motif-operation
frequency. G1 `formal_arc_consistency_q`, `ending_closure_q`, or any single
"higher is better" value is insufficient to distinguish these arrangements.

### Project-stage clustering and listening

The plan alone does **not** contain sounded role masks, actual note density,
drum/bass onset distribution, chord voicing, lattice pitch exposure or
motif binding. `cluster_symbolic_songs.py` adds these Project-derived features
and G1 diagnostics; its 16 medoids cover the 245 symbolically valid songs.
Project feature extraction and clustering took **13.04 s**.

```sh
backend/.venv/bin/python backend/tools/cluster_symbolic_songs.py \
  --cohort local_authority/section_variation_symbolic_1000 --clusters 16 \
  --output local_authority/section_variation_symbolic_1000/clusters_16.json

backend/.venv/bin/python backend/tools/render_symbolic_cluster_representatives.py \
  --cohort local_authority/section_variation_symbolic_1000 \
  --clusters local_authority/section_variation_symbolic_1000/clusters_16.json \
  --output local_authority/section_variation_listening_16 --workers 2
```

The saved Projects are rendered **without recompilation**. The listening set
is `local_authority/section_variation_listening_16/listening_index.md`; the
same directory has `representatives.m3u` for sequential playback. Cluster
medoids: `14, 104, 125, 228, 304, 406, 433, 500, 515, 582, 617, 621,
717, 758, 823, 888`. The audio seeds for clusters 104, 515, 758, 823 are
their nearest renderable members `752, 392, 619, 730` because the medoids
exceeded the stock instrument frequency envelope. Cluster 304 had no
renderable member; its medoid is an explicitly marked **listening preview**
with a widened frequency envelope and separately bound preview Project and
catalog. The exact note ratios are not rounded. The other 15 WAVs passed the
PCM check and full G0. The widened preview is not archive-eligible.

The 16 WAVs show differences to listen for; cluster separation is not a
perceptual score. Compare each medoid to another member of a large cluster
after listening to test whether the feature distance is musically useful.
