"""Verify the PIL contract section 2 schema-hash bindings against reality.

The normative contract ``docs/song_program_perceptual_interpretation_layer_contract.md``
lists the exact raw-byte SHA-256 values of the Phase 1 launch profile schemas.
This tool cross-checks three sources that must agree:

1. the hashes declared in the contract document;
2. the actual raw bytes of the schema files in
   ``backend/songprogram_conformance/schemas/`` (read-only here);
3. the binding constants embedded in ``backend/app/songprogram/perceptual.py``.

Any drift is a hard failure: either the contract, the schema pack, or the
implementation silently moved, which section 2 forbids.  The tool never writes
anything.

Run from the backend directory:

    python tools/check_pil_contract_schema_hashes.py
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
CONTRACT = REPO / "docs" / "song_program_perceptual_interpretation_layer_contract.md"
SCHEMA_DIR = BACKEND / "songprogram_conformance" / "schemas"
IMPLEMENTATION = BACKEND / "app" / "songprogram" / "perceptual.py"

# Contract display name -> (schema file, perceptual.py constant, contract label regex).
BINDINGS = [
    (
        "ArrangementProject 1.2 schema",
        "arrangement_project_1_2.schema.json",
        "PROJECT_SCHEMA_HASH",
    ),
    (
        "SegmentationPolicy 1.0 schema",
        "perceptual_segmentation_policy.schema.json",
        "SEGMENTATION_POLICY_SCHEMA_HASH",
    ),
    (
        "ChordFeatureSpec 1.0 schema",
        "perceptual_chord_feature_spec.schema.json",
        "CHORD_FEATURE_SPEC_SCHEMA_HASH",
    ),
    (
        "ChordFeatureRecord 1.0 schema",
        "perceptual_chord_feature_record.schema.json",
        "CHORD_FEATURE_RECORD_SCHEMA_HASH",
    ),
    (
        "ChordVocabulary 1.0 schema",
        "perceptual_chord_vocabulary.schema.json",
        "CHORD_VOCABULARY_SCHEMA_HASH",
    ),
    (
        # The report schema is the output shape, not an input asset, so
        # perceptual.py embeds no constant for it; the binding is realized by
        # the conformance schema pack.  Contract and file must still agree.
        "PerceptualInterpretationReport 1.0 Phase 4 schema",
        "perceptual_interpretation_report.schema.json",
        None,
    ),
    (
        "VoiceMatchingPolicy 1.0 schema",
        "perceptual_voice_matching_policy.schema.json",
        "VOICE_MATCHING_POLICY_SCHEMA_HASH",
    ),
    (
        "VoiceMatchingRecord 1.0 schema",
        "perceptual_voice_matching_record.schema.json",
        "VOICE_MATCHING_RECORD_SCHEMA_HASH",
    ),
    (
        "TransitionFeatureRecord 1.0 schema",
        "perceptual_transition_feature_record.schema.json",
        "TRANSITION_FEATURE_RECORD_SCHEMA_HASH",
    ),
    (
        "TrajectoryTemplateSet 1.0 schema",
        "perceptual_trajectory_template_set.schema.json",
        "TRAJECTORY_TEMPLATE_SET_SCHEMA_HASH",
    ),
    (
        "TrajectoryInterpretation 1.0 schema",
        "perceptual_trajectory_result.schema.json",
        "TRAJECTORY_RESULT_SCHEMA_HASH",
    ),
]

NUMERIC_CONTRACT_LABEL = "Numeric Contract `cps-numeric/decimal-log2-rhe-v1`"

HASH_RE = re.compile(r"sha256:([0-9a-f]{64})")


def _contract_hashes(text: str) -> dict[str, str]:
    """Map each contract bullet label to its declared hash."""
    result: dict[str, str] = {}
    label: str | None = None
    for line in text.splitlines():
        if line.startswith("- "):
            label = line[2:].split(":", 1)[0].strip()
        match = HASH_RE.search(line)
        if match is not None and label is not None:
            result[label] = "sha256:" + match.group(1)
            label = None
    return result


def _implementation_constants(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    # Captures both `NAME = "sha256:..."` and parenthesized multi-line forms.
    for match in re.finditer(
        r"([A-Z0-9_]+)\s*=\s*\(?\s*\"(sha256:[0-9a-f]{64})\"", text
    ):
        result[match.group(1)] = match.group(2)
    return result


def main() -> int:
    failures: list[str] = []
    contract_text = CONTRACT.read_text(encoding="utf-8")
    impl_text = IMPLEMENTATION.read_text(encoding="utf-8")
    contract_hashes = _contract_hashes(contract_text)
    impl_constants = _implementation_constants(impl_text)

    for label, filename, constant in BINDINGS:
        declared = contract_hashes.get(label)
        if declared is None:
            failures.append(f"contract: no hash bullet found for {label!r}")
            continue
        path = SCHEMA_DIR / filename
        if not path.exists():
            failures.append(f"schemas: missing file {filename}")
            continue
        actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != declared:
            failures.append(f"{label}: schema file {actual} != contract {declared}")
        if constant is not None:
            embedded = impl_constants.get(constant)
            if embedded is None:
                failures.append(f"perceptual.py: constant {constant} not found")
            elif embedded != declared:
                failures.append(f"{label}: perceptual.py {embedded} != contract {declared}")

    # The Numeric Contract has no schema file; contract and implementation must agree.
    numeric_declared = contract_hashes.get(NUMERIC_CONTRACT_LABEL)
    numeric_embedded = impl_constants.get("NUMERIC_CONTRACT_HASH")
    if numeric_declared is None:
        failures.append("contract: Numeric Contract hash bullet not found")
    elif numeric_embedded != numeric_declared:
        failures.append(
            f"Numeric Contract: perceptual.py {numeric_embedded} != contract {numeric_declared}"
        )

    # Build identities: contract names pil.phase3.1.0.0 / pil.phase4.1.0.0.
    for build_id in ("pil.phase3.1.0.0", "pil.phase4.1.0.0"):
        if build_id not in contract_text:
            failures.append(f"contract: build identity {build_id} not mentioned")
        if f'"{build_id}"' not in impl_text:
            failures.append(f"perceptual.py: build identity {build_id} not embedded")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print(f"pil contract schema hashes: OK ({len(BINDINGS)} schema bindings + numeric contract)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
