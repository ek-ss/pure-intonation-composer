#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 1 || ( $# -eq 1 && "$1" != "--dry-run" ) ]]; then
  echo "Usage: $0 [--dry-run]" >&2
  exit 2
fi

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="$ROOT/backend/.venv/bin/python"
PROFILES="$ROOT/backend/songprogram_conformance/profiles"
OUTPUT_ROOT="${OUTPUT_ROOT:-$ROOT/local_authority/section_variation_experiment_v1}"
SEED_OFFSET="${SEED_OFFSET:-0}"
ROUNDS="${ROUNDS:-1}"
CANDIDATES_PER_ROUND="${CANDIDATES_PER_ROUND:-2}"
PIANO_STYLE="${PIANO_STYLE:-none}"
GENERATION_MANIFEST="${GENERATION_MANIFEST:-$PROFILES/full_song_generation_v1.json}"

"$PYTHON" "$ROOT/backend/tools/build_section_variation_profiles.py" --check

for name in baseline section_variation; do
  if [[ "$name" == baseline ]]; then
    profile="$PROFILES/composition_generation_v2.json"
    realization="$PROFILES/composition_realization_v2_1.json"
  else
    profile="$PROFILES/g1_experiments/section_variation.json"
    realization="$PROFILES/g1_experiments/section_variation_roles.json"
  fi
  command=(
    "$PYTHON" "$ROOT/backend/tools/run_composition_g1_exploration.py"
    --profile "$profile" --realization-profile "$realization"
    --generation-manifest "$GENERATION_MANIFEST"
    --seed-offset "$SEED_OFFSET" --rounds "$ROUNDS"
    --candidates-per-round "$CANDIDATES_PER_ROUND"
    --piano-style "$PIANO_STYLE" --output "$OUTPUT_ROOT/$name"
  )
  printf '%s:' "$name"
  printf ' %q' "${command[@]}"
  printf '\n'
  if [[ "${1:-}" != "--dry-run" ]]; then
    "${command[@]}"
  fi
done
