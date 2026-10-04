"""Cluster validated piano v3 cadence trials by deterministic symbolic features.

This experimental CLI reads the per-seed artifacts written by
``generate_piano_v3_cadence_trial.py`` (one ``seed-*`` directory per seed,
each carrying either a success ``report.json`` or a staged ``failure.json``)
and clusters the *validated* successful songs with the shared deterministic
medoid ``cluster(rows, n, metric=...)``.

Design notes (see the feature contract below):

* **Fail-closed validation.**  Every success is re-validated against its
  artifacts: plan / cadence / program / project hashes are recomputed, the
  equave is bound across report / policy / cadence plan / program lattice /
  project lattice, the seed is bound to the plan's and program's recorded
  seeds, the sealed harmony dictionary is seal-verified and its identity must
  agree with the cadence plan, policy, and report, and the impact report is
  *recomputed* from (cadence, program, project, sealed dictionary,
  register-lift policy) and must byte-match the saved artifact with every
  slot reconciled as ``matched`` (an empty or forged slot list cannot pass);
  the report's ``slot_bindings`` must equal the generator's projection of the
  recomputed impact slots in full.  The Project is then verified by a full
  *deterministic recompile* (re-derived compiler identity, sealed dictionary,
  the report's register-lift policy and crossing-match) that must byte-match
  the saved artifact, the evaluation MIDI is re-exported from the verified
  Project and must byte-match, and a rendered PCM report must equal the
  generator's ``_pcm_check`` of the WAV (corrupt or silent audio is rejected).
  A success that fails any check is kept in the cohort denominator but
  reported separately as a *validation* failure with a deterministic reason
  and never clustered; a malformed failure record is a generation failure,
  and neither aborts the cohort.
* **Separate cohorts.**  A cohort is for a single equave; mixed equaves fail
  closed.  Crossing policies and register-lift policy hashes are likewise not
  mixed among the clustered successes.
* **Scoped provenance.**  The progression query is not persisted in the
  Project, so the crossing-match claim is taken as recorded by the trial
  report (the report says so explicitly) and only supported values are
  accepted; it is an *input* to the recompile, so the project verification is
  full except for that one scoped claim.  The register-lift policy is
  additionally cross-bound to the recomputed impact report, which re-derives
  every slot's expected variant from the sealed dictionary.
* **Absolute register.**  The per-role register features are the mean and
  spread of ``log2`` of the events' *final sounding ratios* (millicents),
  not the lattice equave exponent, which is relative to the domain equave and
  is not an octave outside the 2/1 domain.
* **Interpretable cadence features.**  The cadence-specific features come from
  the *actual* cadence slot bindings (the cadence plan's T/D/S function,
  expectation, generator, voice count, root ratio, and voice-leading relaxation)
  and from the *realized* Project (per-role register = absolute log2 of the final sounding ratios, onset
  distribution, density, and chord span from the resolved chords' absolute
  ratios).  Form/section structure is included where suitable.  The Plan's
  function labels and the dictionary ``stability_q`` are **not** used as
  independent auditory truth, and lattice exposure / G1 metrics are not part of
  this feature set (so they cannot be the sole quality indicator).
* **No audio-quality claim.**  A ``--skip-wav`` trial records PCM as
  ``not_evaluated``; a rendered trial records ``checked``.  Neither implies any
  musical/audio quality judgement.

The written report is versioned, explicitly ``non_authoritative``, and carries
a deterministic hash over its body plus the representative (medoid) seeds.

Example::

    python tools/cluster_piano_v3_cadence.py \
        --cohort local_authority/piano_v3_cadence_2_1 \
        --output local_authority/piano_v3_cadence_2_1_clusters.json \
        --clusters 8
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import wave
from collections import Counter
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.harmony_dictionary.storage import read_sealed  # noqa: E402
from app.songprogram.compiler import CompilerIdentity, compile_sp0  # noqa: E402
from app.songprogram.composition_generation import composition_plan_hash  # noqa: E402
from app.songprogram.midi_export import export_evaluation_midi  # noqa: E402
from app.songprogram.mutation import program_hash  # noqa: E402
from app.songprogram.piano_v3 import (  # noqa: E402
    PIANO_V3_DOMAINS,
    build_cadence_policy,
    cadence_impact_report,
    lower_cadence_plan,
    validate_cadence_plan,
    validate_cadence_policy,
)
from app.songprogram.perceptual import project_hash  # noqa: E402
from app.songprogram.search import canonical_bytes  # noqa: E402
from app.songprogram.sparse_variant import (  # noqa: E402
    register_lift_policy_hash,
    validate_register_lift_policy,
)
from app.songprogram.style_profile import (  # noqa: E402
    apply_style_profile,
    style_profile_hash,
    validate_style_profile,
)
from tools.cluster_section_seed_plans import (  # noqa: E402
    cluster,
    distance,
    features as plan_features,
)
from tools.generate_piano_v3_cadence_trial import (  # noqa: E402
    GENERATION_PROFILE,
    _object,
    _base_program,
    _json_bytes,
    _pcm_check,
    _piano_catalog,
)

SCHEMA = "cps.piano-v3-cadence-clusters"
SCHEMA_VERSION = "1.1.0"
HASH_DOMAIN = b"cps.piano-v3-cadence-clusters/v1\0"

# The generation CLI's per-cohort record (one outcome per requested seed).
# When present, the cluster denominator must agree with it exactly.
COHORT_REPORT_SCHEMA = "cps.piano-v3-cadence-cohort-report"
COHORT_REPORT_VERSION = "1.0.0"
# v3: the register distance term was normalized against milli-octave windows
# although its values are millicents, inflating its weight 1200x; v3 fixes the
# unit (millicent windows) and renames the descriptions to match.  The raw
# register feature values are unchanged from v2 (still millicents); what changes
# is the distance metric, and therefore cluster assignments.  v1/v2 reports are
# regenerable, not comparable.
FEATURE_CONTRACT = "cadence-symbolic-distance/v3"

TRIAL_REPORT_SCHEMA = "cps.piano-v3-cadence-trial-report"
# 1.2.0 adds the experimental style-profile provenance fields (``style_profile``
# and ``style_profile_hash``); 1.1.0 is the pre-style report and is still
# accepted so existing cohorts validate unchanged (a 1.1.0 report has no style
# fields and is treated as the baseline).
TRIAL_REPORT_VERSIONS = ("1.1.0", "1.2.0")

CROSSING_MATCHES = ("canonical", "non_crossing")
ROLES = ("harmony", "melody")
CADENCE_FUNCTIONS = ("T", "D", "S")
EXPECTATIONS = ("stable", "depart", "prepare", "arrive", "open")
VOICE_COUNTS = (3, 4)
GENERATORS = (2, 3, 5, 7, 11, 13)

# Artifacts a success must carry for the integrity checks below.
REQUIRED_ARTIFACTS = (
    "composition_plan.json",
    "cadence_policy.json",
    "cadence_plan.json",
    "program.json",
    "project.json",
    "cadence_impact_report.json",
    "evaluation_reference.mid",
    "evaluation_reference_midi.json",
)

# Sealed five-dimensional harmony dictionaries (one per equave), as the
# generation tool reads them.  The impact-report recomputation needs the sealed
# dictionary to re-derive each slot's expected variant.
DICTIONARY_DIR = BACKEND / "harmony_dictionary_data"

# The sealed dictionary is an immutable, hash-verified artifact; cache it per
# equave so a large cohort does not re-read and re-verify the file per seed.
_DICTIONARY_CACHE: dict[str, dict] = {}

# Compiler identity constants, mirroring the generation tool's construction
# (the identity is a deterministic function of the equave and the piano
# instrument catalog; re-deriving it keeps the recompile independent of the
# report).
RESOLVER_BUILD_ID = "sparse-exact/v1"
RESOLVER_PROFILE_HASH = "sha256:" + "10" * 32
BUDGET_PROFILE_DIGEST = "sha256:" + "11" * 32

# The piano instrument catalog is equave-independent; derive its digest once.
_CATALOG_DIGEST: str | None = None


def _mc(value: Fraction) -> int:
    """Millicents of a ratio (mirrors the compiler's exact conversion)."""
    with localcontext() as context:
        context.prec = 112
        result = (
            Decimal(1_200_000)
            * (Decimal(value.numerator).ln() - Decimal(value.denominator).ln())
            / Decimal(2).ln()
        )
        return int(result.to_integral_value(rounding=ROUND_HALF_EVEN))


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _relative(path: Path) -> str:
    """Repo-relative when possible, absolute otherwise (keeps run() testable)."""
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO))
    except ValueError:
        return str(resolved)


def _sealed_dictionary(equave: str) -> dict:
    """Load and seal-verify the per-equave harmony dictionary (cached).

    Mirrors the generation tool's ``_dictionary``.  Raises ``StorageError``
    (a ``ValueError``) when the file is missing, corrupt, or tampered.
    """
    if equave not in _DICTIONARY_CACHE:
        file = DICTIONARY_DIR / f"harmony_dictionary_{equave.replace('/', '-')}.json"
        _DICTIONARY_CACHE[equave] = read_sealed(file, f"harmony-dictionary/{equave}")
    return _DICTIONARY_CACHE[equave]


def _catalog_digest() -> str:
    """Re-derive the piano instrument-catalog digest (mirrors the generator).

    The generation tool widens the piano sample window and re-seals the
    catalog before compiling; the digest is part of the compiler identity.
    """
    global _CATALOG_DIGEST
    if _CATALOG_DIGEST is None:
        generation = _object(GENERATION_PROFILE)
        catalog, _, _, _ = _piano_catalog(generation)
        for entry in catalog["entries"]:
            if entry.get("instrument_id") in ("piano_solo_harmony", "piano_solo_melody"):
                entry["instrument_id"] = f"piano_v3_{entry['role']}"
            if entry.get("kind") == "pitched":
                entry["allowed_frequency_millihz"] = [55_000, 1_760_000]
        _CATALOG_DIGEST = "sha256:" + hashlib.sha256(
            b"cps.instrument-catalog/v1\0" + canonical_bytes(catalog)
        ).hexdigest()
    return _CATALOG_DIGEST


def _compiler_identity(equave: str) -> CompilerIdentity:
    """Re-derive the compiler identity exactly as the generation tool does."""
    return CompilerIdentity(
        f"piano-v3-cadence-{equave.replace('/', '-')}/v1",
        RESOLVER_BUILD_ID,
        RESOLVER_PROFILE_HASH,
        BUDGET_PROFILE_DIGEST,
        _catalog_digest(),
    )


def _stable_reason(error: BaseException) -> str:
    """A deterministic, machine-readable reason for a per-seed validation failure."""
    code = getattr(error, "code", None)
    if isinstance(code, str) and code:
        return f"{type(error).__name__}:{code}"
    if isinstance(error, json.JSONDecodeError):
        return "MALFORMED_JSON"
    if isinstance(error, ValueError):
        return str(error)
    return type(error).__name__


def features(plan: dict, cadence: dict, project: dict) -> dict:
    """Interpretable symbolic features for one validated v3 cadence song.

    The feature set is deliberately built from *realized* content plus
    structural form, not from plan labels or dictionary scores:

    * **form/section** (structural, from the CompositionPlan): opening /
      closure boundaries, the section function sequence, per-function bar and
      energy/density profiles, harmonic-trajectory state shares, and motif
      operation shares (reused from ``cluster_section_seed_plans.features``).
    * **cadence slot bindings** (the cadence plan's actual decisions): T/D/S
      function shares, expectation shares, voice-count shares, generator (prime)
      shares, distinct root-ratio variety, and the share of slots whose voice
      leading was relaxed.  ``stability_q`` is intentionally *not* a feature.
    * **Project events** (the realized sounding): per-role register (mean and
      spread of ``log2`` of the final sounding ratios, in millicents — the
      absolute register, not the equave exponent), onset distribution across
      the bar, and per-role density.
    * **resolved chords** (the realized harmony): mean absolute-ratio span in
      millicents and distinct-chord variety.

    Lattice exposure and G1 metrics are not part of this contract, so neither
    can act as the sole quality indicator.
    """
    result = plan_features(plan)

    slots = cadence["slots"]
    count = max(1, len(slots))
    functions = Counter(slot["function"] for slot in slots)
    expectations = Counter(slot["expectation"] for slot in slots)
    voice_counts = Counter(slot["voice_count"] for slot in slots)
    generators = Counter(slot["generator"] for slot in slots)
    roots = {slot["root_ratio"] for slot in slots}
    relaxed = sum(1 for slot in slots if slot["voice_leading_relaxed"])
    result["cadence_function_share"] = {
        key: round(10_000 * functions[key] / count) for key in CADENCE_FUNCTIONS
    }
    result["cadence_expectation_share"] = {
        key: round(10_000 * expectations[key] / count) for key in EXPECTATIONS
    }
    result["voice_count_share"] = {
        str(key): round(10_000 * voice_counts[key] / count) for key in VOICE_COUNTS
    }
    result["generator_share"] = {
        str(key): round(10_000 * generators[key] / count) for key in GENERATORS
    }
    result["distinct_root_ratio_q"] = round(1_000 * len(roots) / count)
    result["voice_leading_relaxed_q"] = round(10_000 * relaxed / count)

    tracks = {track["id"]: track["role"] for track in project["tracks"]}
    clock = project["clock"]
    bar_ticks = clock["ticks_per_beat"] * clock["beats_per_bar"]
    events = [event for event in project["events"] if event["kind"] == "note"]
    result["register_mean_mc_by_role"] = {}
    result["register_spread_mc_by_role"] = {}
    result["onset_share_by_role"] = {}
    result["events_per_bar_by_role_q"] = {}
    for role in ROLES:
        rows = [event for event in events if tracks[event["track_id"]] == role]
        # Absolute register: log2 of the final sounding ratios, in integer
        # millicents (the canonical artifact encoding forbids floats).  The
        # equave exponent is deliberately *not* used: it is relative to the
        # domain equave, which is not an octave outside the 2/1 domain.
        millicents = [
            _mc(Fraction(event["pitch_provenance"]["final_ratio"]))
            for event in rows
            if "final_ratio" in event.get("pitch_provenance", {})
        ]
        result["register_mean_mc_by_role"][role] = (
            round(sum(millicents) / len(millicents)) if millicents else 0
        )
        result["register_spread_mc_by_role"][role] = (
            max(millicents) - min(millicents) if millicents else 0
        )
        bins = Counter((event["start_tick"] % bar_ticks) * 16 // bar_ticks for event in rows)
        result["onset_share_by_role"][role] = [
            round(10_000 * bins[index] / len(rows)) if rows else 0 for index in range(16)
        ]
        result["events_per_bar_by_role_q"][role] = round(
            1_000 * len(rows) / plan["total_bars"]
        )

    chords = project["resolved_chords"]
    spans = [
        max(_mc(Fraction(ratio)) for ratio in chord["exact_ratios"])
        - min(_mc(Fraction(ratio)) for ratio in chord["exact_ratios"])
        for chord in chords
    ]
    result["chord_span_mc"] = round(sum(spans) / len(spans)) if spans else 0
    occurrences = project["harmony_occurrences"]
    result["distinct_resolved_chords_q"] = round(
        1_000 * len(chords) / max(1, len(occurrences))
    )
    return result


def distance_cadence(left: dict, right: dict) -> float:
    """Deterministic, symmetric distance between two validated v3 cadence songs.

    The base is the shared plan-structure distance (form/section).  On top of
    it the *realized* content is weighted most heavily: the cadence slot-binding
    shares (function / expectation / voice count / generator / root variety /
    leading relaxation) carry double weight, and the per-role register, onset,
    density, and chord-span differences each carry single weight.  Every term
    is normalized so identical songs score exactly ``0``.
    """
    base = distance(left, right)

    share_components = (
        [abs(left["cadence_function_share"][key] - right["cadence_function_share"][key])
         for key in CADENCE_FUNCTIONS]
        + [abs(left["cadence_expectation_share"][key] - right["cadence_expectation_share"][key])
           for key in EXPECTATIONS]
        + [abs(left["voice_count_share"][str(key)] - right["voice_count_share"][str(key)])
           for key in VOICE_COUNTS]
        + [abs(left["generator_share"][str(key)] - right["generator_share"][str(key)])
           for key in GENERATORS]
    )
    cadence = sum(share_components) / (10_000 * len(share_components))
    cadence += (
        abs(left["distinct_root_ratio_q"] - right["distinct_root_ratio_q"]) / 1_000
        + abs(left["voice_leading_relaxed_q"] - right["voice_leading_relaxed_q"]) / 10_000
    )

    # Mean register and spread are both in millicents (absolute log2);
    # normalize against a 4-octave mean window and an 8-octave spread window,
    # expressed in millicents (one octave is 1_200_000 millicents).
    register = sum(
        abs(left["register_mean_mc_by_role"][role]
            - right["register_mean_mc_by_role"][role]) / (4 * 1_200_000)
        + abs(left["register_spread_mc_by_role"][role]
              - right["register_spread_mc_by_role"][role]) / (8 * 1_200_000)
        for role in ROLES
    ) / len(ROLES)

    onset = sum(
        abs(a - b)
        for role in ROLES
        for a, b in zip(left["onset_share_by_role"][role], right["onset_share_by_role"][role])
    ) / (10_000 * len(ROLES))
    density = sum(
        abs(left["events_per_bar_by_role_q"][role] - right["events_per_bar_by_role_q"][role])
        for role in ROLES
    ) / (4_000 * len(ROLES))

    chord = (
        abs(left["chord_span_mc"] - right["chord_span_mc"]) / 1_000_000
        + abs(left["distinct_resolved_chords_q"] - right["distinct_resolved_chords_q"]) / 1_000
    )

    return base + 2 * cadence + register + onset + density + chord


def validate_success(directory: Path, seed: int) -> tuple[dict, dict, dict, dict, dict]:
    """Fail-closed integrity validation of one success directory.

    Returns ``(plan, cadence, program, project, report)`` or raises
    ``ValueError`` with a stable reason.  Every check is recomputed from the
    artifacts on disk; nothing is trusted from the report alone:

    * the equave is bound across report / cadence policy / cadence plan /
      program lattice / project lattice, so a cross-equave forgery fails;
    * the cadence plan is bound to the policy (``policy_hash``) and both are
      bound to the report's stability-profile hash;
    * the sealed per-equave harmony dictionary is seal-verified and its hash,
      equave, stability profile, and thresholds version must agree with the
      cadence plan and report;
    * the impact report is **recomputed** from (cadence, program, project,
      sealed dictionary, register-lift policy) and must byte-match the saved
      artifact with every slot reconciled as ``matched`` — an empty or forged
      slot list cannot pass;
    * the report's ``slot_bindings`` must equal, in full content, the
      generator's projection of the recomputed impact slots;
    * the seed is bound to the plan's and program's recorded seeds, and the
      project's ``source_program`` reference must bind to the program;
    * the compiler identity is re-derived (not trusted from the report) and
      must match both the project's compiler section and the report; the
      Project is then verified by a full deterministic recompile that must
      byte-match the saved artifact;
    * the evaluation MIDI is re-exported from the verified Project and must
      byte-match the saved file (in addition to its manifest hash);
    * a rendered PCM report must equal the generator's ``_pcm_check`` of the
      WAV in full (corrupt or silent audio is rejected); a skipped render is
      ``not_evaluated`` and never implies audio quality;
    * the register-lift policy is internally hash-consistent and its hash
      matches the report; the crossing-match claim must be a supported value.
    """
    report = _load(directory / "report.json")
    if not isinstance(report, dict):
        raise ValueError(f"report is not an object: {directory.name}")
    if (report.get("schema") != TRIAL_REPORT_SCHEMA
            or report.get("schema_version") not in TRIAL_REPORT_VERSIONS):
        raise ValueError(f"report schema mismatch: {directory.name}")
    if report.get("status") != "success":
        raise ValueError(f"report status not success: {directory.name}")
    if report.get("seed") != seed:
        raise ValueError(f"report seed mismatch: {directory.name}")

    for name in REQUIRED_ARTIFACTS:
        if not (directory / name).is_file():
            raise ValueError(f"missing artifact {name}: {directory.name}")

    plan = _load(directory / "composition_plan.json")
    policy = _load(directory / "cadence_policy.json")
    cadence = _load(directory / "cadence_plan.json")
    program = _load(directory / "program.json")
    project = _load(directory / "project.json")

    # Equave bound across every artifact that carries a lattice.
    equave = report["equave"]
    if equave not in PIANO_V3_DOMAINS:
        raise ValueError(f"unsupported equave {equave!r}: {directory.name}")
    if policy["equave"] != equave:
        raise ValueError(f"cadence policy equave mismatch: {directory.name}")
    if cadence["equave"] != equave:
        raise ValueError(f"cadence plan equave mismatch: {directory.name}")
    if program["lattice"]["equave"] != equave:
        raise ValueError(f"program lattice equave mismatch: {directory.name}")
    if project["lattice"]["equave"] != equave:
        raise ValueError(f"project lattice equave mismatch: {directory.name}")

    # Seed bound to the plan's and program's recorded seeds (both are inside
    # the hash-verified bodies, so a report-only seed edit cannot pass).
    if plan["seed"] != report["seed"]:
        raise ValueError(f"plan seed mismatch: {directory.name}")
    if program["seed"] != report["seed"]:
        raise ValueError(f"program seed mismatch: {directory.name}")

    # Plan hash (recomputed) must equal the report's and the plan's own.
    if (composition_plan_hash(plan) != report["composition_plan_hash"]
            or plan.get("plan_hash") != report["composition_plan_hash"]):
        raise ValueError(f"composition plan hash mismatch: {directory.name}")

    # Cadence plan: internal hash + binding to the plan and to the policy.
    validate_cadence_plan(cadence)
    if cadence["cadence_plan_hash"] != report["cadence_plan_hash"]:
        raise ValueError(f"cadence plan hash mismatch: {directory.name}")
    if cadence.get("source_plan_hash") != report["composition_plan_hash"]:
        raise ValueError(f"cadence source plan mismatch: {directory.name}")
    if cadence["policy_hash"] != report["cadence_policy_hash"]:
        raise ValueError(f"cadence-to-policy binding mismatch: {directory.name}")

    # Cadence policy: internal consistency + hash bindings to the report.
    validate_cadence_policy(policy)
    if policy["policy_hash"] != report["cadence_policy_hash"]:
        raise ValueError(f"cadence policy hash mismatch: {directory.name}")
    if policy["stability_profile_hash"] != report["stability_profile_hash"]:
        raise ValueError(f"policy stability hash mismatch: {directory.name}")
    if cadence["stability_profile_hash"] != report["stability_profile_hash"]:
        raise ValueError(f"cadence stability hash mismatch: {directory.name}")

    # Register-lift policy: internal consistency (hash matches the body).
    validate_register_lift_policy(report["register_lift_policy"])
    if report["register_lift_policy_hash"] != register_lift_policy_hash(
            report["register_lift_policy"]):
        raise ValueError(f"register lift policy hash mismatch: {directory.name}")

    # The crossing-match claim must be a supported value (the progression
    # query itself is not persisted in the Project, so it cannot be re-derived).
    if report["crossing_match"] not in CROSSING_MATCHES:
        raise ValueError(f"unsupported crossing match {report['crossing_match']!r}: "
                         f"{directory.name}")

    # Experimental style profile: ``None`` (or absent, as in 1.1.0 reports) is
    # the baseline (no style).  A present profile must validate and its
    # recomputed hash must equal the report's; a hash without a body (or vice
    # versa) is inconsistent.  The profile is an unsealed control configuration
    # (no auditory claim); it is provenance, not a quality judgement.
    style_profile = report.get("style_profile")
    if style_profile is None:
        if report.get("style_profile_hash") is not None:
            raise ValueError(f"style profile hash without profile: {directory.name}")
    else:
        try:
            validate_style_profile(style_profile)
        except ValueError as error:
            raise ValueError(
                f"style profile invalid: {error}: {directory.name}"
            ) from error
        if report.get("style_profile_hash") != style_profile_hash(style_profile):
            raise ValueError(f"style profile hash mismatch: {directory.name}")

    # Program / Project artifact hashes (recomputed).
    if program_hash(program) != report["program_hash"]:
        raise ValueError(f"program hash mismatch: {directory.name}")
    if project_hash(project) != report["project_hash"]:
        raise ValueError(f"project hash mismatch: {directory.name}")

    # The project's source-program reference must bind to the same program.
    source_program = project.get("source_program")
    if (not isinstance(source_program, dict)
            or source_program.get("hash") != report["program_hash"]):
        raise ValueError(f"project source program mismatch: {directory.name}")

    # Sealed dictionary: seal-verified, and its identity must agree with the
    # cadence plan, policy, and report.
    dictionary = _sealed_dictionary(equave)
    if dictionary["hash"] != report["dictionary_hash"]:
        raise ValueError(f"sealed dictionary hash mismatch: {directory.name}")
    if dictionary["equave"] != equave:
        raise ValueError(f"sealed dictionary equave mismatch: {directory.name}")
    if (cadence["dictionary_hash"] != report["dictionary_hash"]
            or policy["dictionary_hash"] != report["dictionary_hash"]):
        raise ValueError(f"dictionary hash mismatch: {directory.name}")
    if cadence["stability_profile_hash"] != dictionary["stability_profile_hash"]:
        raise ValueError(f"dictionary stability hash mismatch: {directory.name}")
    if cadence["thresholds_version"] != dictionary["thresholds"]["version"]:
        raise ValueError(f"dictionary thresholds version mismatch: {directory.name}")

    # Re-derive policy and realized Program from the already-verified inputs.
    # Artifact self-hashes alone do not prove that they correspond to the
    # reported style profile (or to the baseline when no profile is present).
    cadence_kwargs = {}
    if style_profile is not None:
        cadence_kwargs = {
            "voice_leading_cap_cents": (
                style_profile["cadence"]["voice_leading_cap_millicents"] / 1000.0
            ),
            "candidate_budget": style_profile["cadence"]["candidate_budget"],
        }
    expected_policy = build_cadence_policy(
        equave, dictionary["hash"], dictionary["stability_profile_hash"],
        dictionary["thresholds"]["version"], **cadence_kwargs,
    )
    if _json_bytes(expected_policy) != (directory / "cadence_policy.json").read_bytes():
        raise ValueError(f"cadence policy does not match inputs: {directory.name}")

    # Impact report: recompute from the sealed inputs and require byte-equality
    # with the saved artifact.  This defeats an empty or forged slot list and
    # binds the register-lift policy between report and impact artifact.
    try:
        recomputed = cadence_impact_report(
            cadence, program, project,
            dictionary_file=dictionary,
            register_lift_policy=report["register_lift_policy"],
        )
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError(
            f"impact report recomputation failed: "
            f"{getattr(error, 'code', type(error).__name__)}: {directory.name}"
        ) from error
    if canonical_bytes(recomputed) != (directory / "cadence_impact_report.json").read_bytes():
        raise ValueError(f"impact report recomputation mismatch: {directory.name}")
    if not recomputed["slots"]:
        raise ValueError(f"empty impact report slots: {directory.name}")
    if len(recomputed["slots"]) != len(cadence["slots"]):
        raise ValueError(f"impact slot count mismatch: {directory.name}")
    if any(row["status"] != "matched" for row in recomputed["slots"]):
        raise ValueError(f"impact slot not matched: {directory.name}")

    # Report counts must reflect the full reconciliation, and slot_bindings
    # must equal — in full content, mirroring the generator's construction —
    # the projection of the recomputed impact slots.
    if (report["candidate_slots"] != len(cadence["slots"])
            or report["matched_slots"] != len(cadence["slots"])):
        raise ValueError(f"slot count mismatch: {directory.name}")
    projected_bindings = [
        {
            "section_id": row["section_id"],
            "bar": row["bar"],
            "source_chord_key": row["planned_variant"],
            "source_dictionary_hash": row["source_dictionary_hash"],
            "program_variant_hashes": row.get("program_variant_hashes", []),
            "absolute_exact_ratios": row["planned_absolute_ratios"],
            "project_chords": row.get("project_chords", []),
            "mismatches": row["mismatches"],
            "status": row["status"],
        }
        for row in recomputed["slots"]
    ]
    if report["slot_bindings"] != projected_bindings:
        raise ValueError(f"slot bindings differ from recomputed impact: {directory.name}")

    catalog_digest = _catalog_digest()
    try:
        expected_program = lower_cadence_plan(
            _base_program(plan, equave, catalog_digest), cadence, dictionary,
        )
        if style_profile is not None:
            expected_program = apply_style_profile(expected_program, style_profile)
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError(f"program re-derivation failed: {directory.name}") from error
    if canonical_bytes(expected_program) != (directory / "program.json").read_bytes():
        raise ValueError(f"program does not match cadence/style inputs: {directory.name}")

    # Compiler identity: re-derived (never trusted from the report) and bound
    # to both the project's compiler section and the report.
    identity = _compiler_identity(equave)
    if project.get("compiler") != identity.__dict__:
        raise ValueError(f"project compiler identity mismatch: {directory.name}")
    if report.get("compiler_identity") != identity.__dict__:
        raise ValueError(f"report compiler identity mismatch: {directory.name}")

    # Full deterministic recompile of the Project (byte-equal).  This binds
    # every realized note event, chord, and occurrence to the verified
    # program, sealed dictionary, register-lift policy, and crossing-match.
    try:
        recompiled = compile_sp0(
            program, identity, stochastic_realization=False,
            dictionary_authorities={dictionary["hash"]: dictionary},
            progression_diagnostics={},
            register_lift_policy=report["register_lift_policy"],
            crossing_match=report["crossing_match"],
        )
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError(
            f"project recompile failed: "
            f"{getattr(error, 'code', type(error).__name__)}: {directory.name}"
        ) from error
    if canonical_bytes(recompiled) != (directory / "project.json").read_bytes():
        raise ValueError(f"project recompile mismatch: {directory.name}")

    # MIDI: manifest hash plus a full re-export from the verified Project.
    midi = (directory / "evaluation_reference.mid").read_bytes()
    if not midi:
        raise ValueError(f"empty evaluation MIDI: {directory.name}")
    manifest = _load(directory / "evaluation_reference_midi.json")
    if manifest["midi_hash"] != "sha256:" + hashlib.sha256(midi).hexdigest():
        raise ValueError(f"MIDI hash mismatch: {directory.name}")
    try:
        reexported, _ = export_evaluation_midi(
            project, program_by_track={"harmony": 0, "melody": 0}
        )
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError(
            f"MIDI re-export failed: "
            f"{getattr(error, 'code', type(error).__name__)}: {directory.name}"
        ) from error
    if reexported != midi:
        raise ValueError(f"MIDI re-export mismatch: {directory.name}")

    # PCM: distinguish not_evaluated (skip-wav) from checked; never a quality
    # claim.  A checked report must equal the generator's _pcm_check of the
    # WAV in full (corrupt or silent audio raises and is rejected).
    pcm = report.get("pcm")
    if not isinstance(pcm, dict):
        raise ValueError(f"pcm is not an object: {directory.name}")
    if pcm.get("status") == "checked":
        wav = directory / "reference.wav"
        if not wav.is_file():
            raise ValueError(f"missing reference WAV: {directory.name}")
        try:
            recomputed_pcm = _pcm_check(wav.read_bytes())
        except (ValueError, OSError, struct.error, EOFError, wave.Error) as error:
            raise ValueError(
                f"reference WAV check failed: "
                f"{getattr(error, 'code', type(error).__name__)}: {directory.name}"
            ) from error
        if recomputed_pcm != pcm:
            raise ValueError(f"PCM report mismatch: {directory.name}")
    elif pcm.get("status") != "not_evaluated":
        raise ValueError(f"unexpected PCM status: {directory.name}")

    return plan, cadence, program, project, report


def clamp_clusters(rows: list[dict], clusters: int) -> int:
    """Deterministic effective cluster count for a set of validated rows.

    Identical feature vectors cannot be split into more clusters than there
    are distinct vectors, so the count clamps to the distinct count (the
    shared medoid dedups identical centers in agreement).  Zero rows clamp to
    zero clusters.
    """
    if not rows:
        return 0
    distinct = len({canonical_bytes(row["features"]) for row in rows})
    return min(clusters, distinct)


def _seed_dir_seed(name: str) -> int:
    """Parse a ``seed-*`` directory name into its seed, fail-closed.

    The canonical name is ``seed-`` followed by the seed's decimal
    representation.  A non-numeric suffix is malformed; a leading-zero suffix
    (``seed-00``) is an alias that would duplicate ``seed-0`` under ``int()``.
    Both are rejected rather than silently reinterpreted.
    """
    suffix = name.removeprefix("seed-")
    if not suffix.isdigit():
        raise ValueError(f"malformed seed directory name {name!r}")
    seed = int(suffix)
    if suffix != str(seed):
        raise ValueError(f"alias seed directory name {name!r} (canonical: seed-{seed})")
    return seed


def _validate_cohort_report(cohort: Path, seed_dirs: list[Path]) -> str:
    """Fail-closed consistency check between ``cohort_report.json`` and the seed directories.

    The generation CLI records one outcome per requested seed, so the cluster
    denominator must not silently diverge from that record.  This validates
    the report's schema, equave, and seed_denominator; requires the outcomes'
    seeds to be unique uint64 values whose exact set equals the seed
    directories (rejecting missing, duplicate, and extra directories); and
    requires each outcome's status to be corroborated by the directory
    contents (a success must carry ``report.json``, a failure
    ``failure.json``).  Returns the report's equave.

    Success outcomes carry the generator's recorded ``report`` path — the
    output path as given on the command line (the documented convention is a
    relative ``local_authority/...`` path; an absolute path is equally valid)
    joined with ``seed-{seed}/report.json``.  The recorded path is bound
    *exactly*: its resolved form must equal this cohort's
    ``seed-{seed}/report.json``.  A suffix match is not sufficient — it would
    accept an unrelated cohort's ``notseed-4/report.json``, which ends with
    ``seed-4/report.json``.
    """
    report = _load(cohort / "cohort_report.json")
    if not isinstance(report, dict):
        raise ValueError(f"cohort_report is not an object: {cohort.name}")
    if (report.get("schema") != COHORT_REPORT_SCHEMA
            or report.get("schema_version") != COHORT_REPORT_VERSION):
        raise ValueError(f"cohort_report schema mismatch: {cohort.name}")
    equave = report.get("equave")
    if not isinstance(equave, str) or equave not in PIANO_V3_DOMAINS:
        raise ValueError(f"cohort_report unsupported equave {equave!r}: {cohort.name}")
    outcomes = report.get("outcomes")
    if not isinstance(outcomes, list):
        raise ValueError(f"cohort_report outcomes is not a list: {cohort.name}")
    denominator = report.get("seed_denominator")
    if not isinstance(denominator, int) or isinstance(denominator, bool) or denominator < 0:
        raise ValueError(f"cohort_report seed_denominator invalid: {cohort.name}")
    if denominator != len(outcomes):
        raise ValueError(
            f"cohort_report seed_denominator {denominator} != {len(outcomes)} outcomes: "
            f"{cohort.name}"
        )
    outcome_seeds: list[int] = []
    for index, outcome in enumerate(outcomes):
        if not isinstance(outcome, dict):
            raise ValueError(f"cohort_report outcome {index} is not an object: {cohort.name}")
        seed = outcome.get("seed")
        if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed < 2**64:
            raise ValueError(f"cohort_report outcome {index} seed invalid {seed!r}: {cohort.name}")
        status = outcome.get("status")
        if status not in ("success", "failed"):
            raise ValueError(
                f"cohort_report outcome {index} status invalid {status!r}: {cohort.name}"
            )
        if status == "success":
            recorded = outcome.get("report")
            if not isinstance(recorded, str) or not recorded:
                raise ValueError(
                    f"cohort_report outcome {index} report path invalid: {cohort.name}"
                )
            # Exact binding (see the docstring): the resolved recorded path
            # must be this cohort's directory/report.json.  A relative
            # recorded path resolves against the current working directory,
            # mirroring how the generation CLI produced it.
            if Path(recorded).resolve() != (cohort / f"seed-{seed}" / "report.json").resolve():
                raise ValueError(
                    f"cohort_report outcome {index} report path does not bind to "
                    f"seed-{seed}/report.json: {cohort.name}"
                )
        outcome_seeds.append(seed)
    if len(set(outcome_seeds)) != len(outcome_seeds):
        raise ValueError(f"cohort_report outcomes contain duplicate seeds: {cohort.name}")
    successes = sum(1 for outcome in outcomes if outcome.get("status") == "success")
    if (report.get("successes") != successes
            or report.get("failures") != len(outcomes) - successes):
        raise ValueError(f"cohort_report success/failure counts inconsistent: {cohort.name}")
    directory_seeds = {int(directory.name.removeprefix("seed-")) for directory in seed_dirs}
    missing = sorted(set(outcome_seeds) - directory_seeds)
    extra = sorted(directory_seeds - set(outcome_seeds))
    if missing or extra:
        raise ValueError(
            f"cohort_report/directory seed mismatch (missing={missing} extra={extra}): "
            f"{cohort.name}"
        )
    for outcome in outcomes:
        directory = cohort / f"seed-{outcome['seed']}"
        if outcome["status"] == "success" and not (directory / "report.json").is_file():
            raise ValueError(
                f"cohort_report success seed {outcome['seed']} missing report.json: "
                f"{cohort.name}"
            )
        if outcome["status"] == "failed" and not (directory / "failure.json").is_file():
            raise ValueError(
                f"cohort_report failure seed {outcome['seed']} missing failure.json: "
                f"{cohort.name}"
            )
    return equave


def run(cohort: Path, output: Path, *, clusters: int = 16) -> dict:
    """Validate a v3 cadence cohort and write the versioned cluster report.

    The cohort denominator is every ``seed-*`` directory; each name must be a
    canonical, unique numeric seed (a non-numeric suffix or a leading-zero
    alias such as ``seed-00`` fails closed instead of duplicating a seed).
    When the generation CLI's ``cohort_report.json`` is present, it must agree
    with the directories exactly — schema, equave, seed_denominator, and one
    unique outcome per directory with statuses corroborated by the directory
    contents — so a missing, duplicate, extra, or malformed seed directory
    fails the run instead of silently lowering the nominal count.  Generation
    failures (``failure.json``) and integrity-validation failures (a
    ``report.json`` that does not survive :func:`validate_success`) are both
    kept in the denominator and reported separately; only validated successes
    are clustered.  Zero validated successes is handled gracefully (an empty
    cluster set, no error).
    """
    if not cohort.is_dir():
        raise ValueError(f"cohort directory missing: {cohort}")
    census: list[tuple[int, Path]] = []
    seen_seeds: set[int] = set()
    for directory in sorted(cohort.glob("seed-*")):
        if not directory.is_dir():
            continue
        seed = _seed_dir_seed(directory.name)
        if seed in seen_seeds:
            raise ValueError(f"duplicate seed directory for seed {seed}: {directory.name}")
        seen_seeds.add(seed)
        census.append((seed, directory))
    seed_dirs = [directory for _, directory in sorted(census)]
    if not seed_dirs:
        raise ValueError(f"no seed directories in cohort: {cohort}")
    # When the generation CLI's cohort report is present, the denominator must
    # agree with it exactly (fail closed on any divergence).
    cohort_equave: str | None = None
    if (cohort / "cohort_report.json").is_file():
        cohort_equave = _validate_cohort_report(cohort, seed_dirs)

    generation_failures: list[dict] = []
    validation_failures: list[dict] = []
    rows: list[dict] = []
    equaves: set[str] = set()

    for directory in seed_dirs:
        seed = int(directory.name.removeprefix("seed-"))
        has_report = (directory / "report.json").is_file()
        has_failure = (directory / "failure.json").is_file()
        if has_report and has_failure:
            validation_failures.append(
                {"seed": seed, "reason": "BOTH_REPORT_AND_FAILURE"}
            )
            continue
        if has_failure:
            # A malformed or non-object failure record is a generation failure
            # with a stable code; it must not abort the cohort.
            try:
                failure = _load(directory / "failure.json")
            except (ValueError, KeyError, TypeError, AttributeError,
                    OSError, json.JSONDecodeError):
                failure = None
            if isinstance(failure, dict):
                # Only a string equave is hashable and meaningful for the
                # cohort-level equave check; a malformed (e.g. list) equave is
                # skipped so it cannot abort the run, while the seed stays in
                # the denominator via the recorded generation failure.
                equave = failure.get("equave")
                if isinstance(equave, str):
                    equaves.add(equave)
                generation_failures.append({
                    "seed": seed,
                    "stage": failure.get("stage"),
                    "failure_code": failure.get("failure_code"),
                })
            else:
                generation_failures.append({
                    "seed": seed,
                    "stage": None,
                    "failure_code": "MALFORMED_FAILURE_RECORD",
                })
            continue
        if not has_report:
            validation_failures.append(
                {"seed": seed, "reason": "NO_REPORT_OR_FAILURE"}
            )
            continue
        # Validation and feature extraction are per-seed: a malformed,
        # non-object, or hash-valid-but-odd artifact is a validation failure,
        # not an abort.
        try:
            plan, cadence, program, project, report = validate_success(directory, seed)
            row_features = features(plan, cadence, project)
        except (ValueError, KeyError, TypeError, AttributeError,
                OSError, json.JSONDecodeError) as error:
            validation_failures.append(
                {"seed": seed, "reason": _stable_reason(error)}
            )
            continue
        equaves.add(report["equave"])
        rows.append({
            "seed": seed,
            "equave": report["equave"],
            "crossing_match": report["crossing_match"],
            "register_lift_policy_hash": report["register_lift_policy_hash"],
            # Experimental style provenance (``None`` = baseline / no style).
            "style_profile_hash": report.get("style_profile_hash"),
            "composition_plan_hash": report["composition_plan_hash"],
            "cadence_plan_hash": report["cadence_plan_hash"],
            "program_hash": report["program_hash"],
            "project_hash": report["project_hash"],
            "pcm_status": report["pcm"]["status"],
            "features": row_features,
        })

    # Separate equave cohorts: a cohort is for exactly one equave.  Only
    # string equaves are comparable; anything else is simply untrusted.
    known_equaves = {equave for equave in equaves if isinstance(equave, str)}
    if len(known_equaves) > 1:
        raise ValueError(f"mixed equaves in cohort: {sorted(known_equaves)}")
    if any(equave not in PIANO_V3_DOMAINS for equave in known_equaves):
        raise ValueError(f"unsupported equave in cohort: {sorted(known_equaves)}")
    if (cohort_equave is not None and known_equaves
            and cohort_equave not in known_equaves):
        raise ValueError(
            f"cohort_report equave {cohort_equave!r} does not match cohort "
            f"{sorted(known_equaves)}"
        )
    # The per-seed records are the primary source; the cohort report's equave
    # is the fallback when every per-seed record is malformed.
    equave = next(iter(known_equaves), cohort_equave)

    # Do not mix crossing policies among the clustered successes.
    crossings = {row["crossing_match"] for row in rows}
    if len(crossings) > 1:
        raise ValueError(f"mixed crossing policies in cohort: {sorted(crossings)}")
    if any(match not in CROSSING_MATCHES for match in crossings):
        raise ValueError(f"unsupported crossing policy: {sorted(crossings)}")
    crossing_match = next(iter(crossings), None)

    # Do not mix register-lift policies among the clustered successes: a
    # different lift policy changes which chord candidates are even generated.
    policy_hashes = {row["register_lift_policy_hash"] for row in rows}
    if len(policy_hashes) > 1:
        raise ValueError(
            f"mixed register lift policies in cohort: {len(policy_hashes)} distinct"
        )
    lift_policy_hash = next(iter(policy_hashes), None)

    # Do not mix experimental styles among the clustered successes: a different
    # style profile changes the realized tempo / dynamics / rhythm / progression,
    # so a mixed cohort would conflate distinct realizations.  ``None`` is the
    # baseline (no style); a cohort mixing baseline and a styled seed (or two
    # different styles) fails closed.
    style_hashes = {row["style_profile_hash"] for row in rows}
    if len(style_hashes) > 1:
        raise ValueError(
            f"mixed style profiles in cohort: {len(style_hashes)} distinct"
        )
    style_profile_hash = next(iter(style_hashes), None)
    # An all-baseline cohort (no style selected) carries no style fields at all,
    # so the report stays byte-identical to the pre-style 1.1.0 reports; a
    # styled cohort records the profile hash per row and at the top level.
    has_style = style_profile_hash is not None
    if not has_style:
        for row in rows:
            del row["style_profile_hash"]

    # Cluster only validated successes; zero successes is a graceful no-op.
    if rows:
        if not 1 <= clusters <= len(rows):
            raise ValueError(
                f"cluster count {clusters} outside validated successes {len(rows)}"
            )
        # Identical feature vectors cannot be split into more clusters than
        # there are distinct vectors; clamp deterministically (the shared
        # medoid dedups identical centers in agreement).
        effective_clusters = clamp_clusters(rows, clusters)
        groups = cluster(rows, effective_clusters, metric=distance_cadence)
    else:
        effective_clusters = 0
        groups = []

    report = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "non_authoritative": True,
        "source_cohort": _relative(cohort),
        "equave": equave,
        "crossing_match": crossing_match,
        # The progression query is not persisted in the Project, so the
        # crossing-match provenance is as recorded by the trial report, not
        # independently re-derived; it is an input to the recompile below.
        "crossing_match_provenance": "trial_report_recorded_not_rederived",
        # The Project is verified by a full deterministic recompile that must
        # byte-match the saved artifact (re-derived compiler identity, sealed
        # dictionary, register-lift policy, crossing-match); the evaluation
        # MIDI is re-exported from it and must byte-match as well.
        "project_verification": "deterministic_recompile_byte_equal",
        "register_lift_policy_hash": lift_policy_hash,
        "requested_clusters": clusters if rows else 0,
        "effective_clusters": effective_clusters,
        "seed_denominator": len(seed_dirs),
        "generation_failure_count": len(generation_failures),
        "generation_failures": generation_failures,
        "validation_failure_count": len(validation_failures),
        "validation_failures": validation_failures,
        "validated_success_count": len(rows),
        "pcm_not_evaluated_count": sum(
            1 for row in rows if row["pcm_status"] == "not_evaluated"
        ),
        "pcm_checked_count": sum(1 for row in rows if row["pcm_status"] == "checked"),
        # PCM status records whether audio was rendered/checked; it is not a
        # musical or audio-quality judgement.
        "audio_quality_assessed": False,
        "feature_contract": FEATURE_CONTRACT,
        "rows": rows,
        "clusters": groups,
        "report_hash": "",
    }
    # Experimental style provenance: recorded only when a non-baseline style is
    # present (an all-baseline cohort omits these fields entirely, keeping the
    # report byte-identical to the pre-style 1.1.0 reports).  The profile is an
    # unsealed control configuration; no auditory T/D/S claim is made.
    if has_style:
        report["style_profile_hash"] = style_profile_hash
        report["style_profile_status"] = "experimental_unsealed"
    body = {key: value for key, value in report.items() if key != "report_hash"}
    report["report_hash"] = "sha256:" + hashlib.sha256(
        HASH_DOMAIN + canonical_bytes(body)
    ).hexdigest()

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.read_bytes() != canonical_bytes(report):
        raise ValueError("existing cluster report differs")
    output.write_bytes(canonical_bytes(report))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--clusters", type=int, default=16)
    args = parser.parse_args()
    if (not args.output.resolve().is_relative_to(REPO / "local_authority")
            or not args.cohort.resolve().is_relative_to(REPO / "local_authority")):
        parser.error("paths must be in local_authority")
    try:
        report = run(args.cohort, args.output, clusters=args.clusters)
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps({
        "equave": report["equave"],
        "crossing_match": report["crossing_match"],
        "denominator": report["seed_denominator"],
        "generation_failures": report["generation_failure_count"],
        "validation_failures": report["validation_failure_count"],
        "validated_successes": report["validated_success_count"],
        "representatives": [row["representative_seed"] for row in report["clusters"]],
        "report_hash": report["report_hash"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
