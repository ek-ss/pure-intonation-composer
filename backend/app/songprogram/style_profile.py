"""Versioned experimental style profiles for piano v3 cadence trials.

A style profile is a versioned, hash-bound object that alters the *realized*
sound of a v3 cadence trial:

* ``tempo_milli_bpm`` — the Program/Project clock tempo (MIDI tempo);
* per-role ``velocity_scale_q`` / ``gate_scale_q`` — note loudness and sustain
  (MIDI velocity / note duration);
* per-role rhythm steps (``at_tick`` / ``duration_ticks`` / ``accent_q``) —
  onset timing, density, and per-note accent;
* the cadence policy's voice-leading cap (stored in integer millicents,
  ``voice_leading_cap_millicents``) and ``candidate_budget`` — which
  sealed-dictionary variants are selected per slot (harmony progression).

The profile is an *experimental control configuration*: it changes how the
composition is realized (Program / Project / MIDI), never the sealed harmony
dictionary, and it keeps the cadence plan's dictionary binding intact (each
slot still binds to a sealed variant; only *which* variant is selected may
differ).  It makes no auditory T/D/S claim and is never sealed.

Two built-in, clearly contrasting profiles are provided:

* ``restrained`` — slow, soft, sustained (a reflective control).
* ``driving`` — fast, loud, staccato (an energetic control).

When no profile is selected the trial reproduces the baseline byte for byte
(the Program / Project / WAV hashes are unchanged).

Validation is fail-closed and includes *cross-field* musical checks that
mirror the compiler's contracts for the v3 pipeline (the one-chord-per-slot
zip contract, the three-point melody zip contract, non-overlapping harmony
occurrences, and every melody note inside exactly one harmony occurrence,
using the compiler's exact gate-scaled durations and onset wrapping).  A
validated profile has schema-valid values and passes those checks, but that
does not *guarantee* a successful compile for every plan (the section
structure can add further constraints, e.g. a note overflowing the last bar
of a one-bar section); generation remains fail-closed.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping

STYLE_PROFILE_SCHEMA = "cps.style-profile"
STYLE_PROFILE_VERSION = "1.0.0"

# Schema-valid value ranges (mirroring the SongProgram 0.3 / cadence-policy
# contracts).  A validated profile has schema-valid values and passes the
# cross-field musical checks below, but that does not guarantee a successful
# compile for every plan; generation remains fail-closed.
_TEMPO_MIN = 30_000
_TEMPO_MAX = 300_000
_VELOCITY_MIN = 0
_VELOCITY_MAX = 10_000
_GATE_MIN = 1
_GATE_MAX = 10_000
_ACCENT_MIN = 0
_ACCENT_MAX = 10_000
_MAX_STEPS = 64
# The cadence policy's voice-leading cap is stored in *integer* millicents so
# the profile body stays float-free (the canonical artifact encoding forbids
# floats).  The cadence policy itself carries the value in cents; the generator
# converts millicents -> cents when it builds the policy.
_CADENCE_CAP_MIN = 0
_CADENCE_CAP_MAX = 1_200_000
_CADENCE_BUDGET_MIN = 1
_CADENCE_BUDGET_MAX = 256


class StyleProfileError(ValueError):
    """A stable style-profile failure with a machine-readable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def style_profile_hash(profile: Mapping[str, Any]) -> str:
    """The profile's provenance hash (over the body, excluding ``profile_hash``)."""
    body = {key: value for key, value in profile.items() if key != "profile_hash"}
    digest = hashlib.sha256(
        b"cps.style-profile/v1\0" + _canonical(body)
    ).hexdigest()
    return "sha256:" + digest


def _check_int(value: Any, low: int, high: int, code: str) -> None:
    if type(value) is not int or isinstance(value, bool) or not low <= value <= high:
        raise StyleProfileError(code, repr(value))


def _check_steps(steps: Any, code: str) -> None:
    if not isinstance(steps, list) or not 1 <= len(steps) <= _MAX_STEPS:
        raise StyleProfileError(code, repr(len(steps) if isinstance(steps, list) else steps))
    for step in steps:
        if not isinstance(step, Mapping) or set(step) != {"at_tick", "duration_ticks", "accent_q"}:
            raise StyleProfileError(code, repr(step))
        _check_int(step["at_tick"], 0, 1_048_576, code)
        _check_int(step["duration_ticks"], 1, 1_048_576, code)
        _check_int(step["accent_q"], _ACCENT_MIN, _ACCENT_MAX, code)


# Cross-field musical constraints (checked in ``validate_style_profile``).
# The v3 pipeline's per-bar rhythm cells run at 4/4 @ 480 ticks/beat, so the
# bar (and each rhythm cell's ``length_ticks``) is 1920 ticks; the compiler
# places a step at ``at_tick % length_ticks`` and realizes its duration as
# ``max(1, round_half_even(duration_ticks * gate_scale_q / 10_000))``.
_TICKS_PER_BAR = 1920
# The v3 melody material (the conformance fixture's ``melody_a``) carries three
# points under a zip mapping, so the compiler accepts at most three melody
# steps (a fourth would raise MAPPING_LENGTH_MISMATCH).
_MELODY_MAX_STEPS = 3


def _round_half_even(numerator: int, denominator: int) -> int:
    """Exact round-half-to-even (mirror of the compiler's ``_rhe``)."""
    sign = -1 if numerator < 0 else 1
    quotient, remainder = divmod(abs(numerator), denominator)
    return sign * (
        quotient
        + int(
            remainder * 2 > denominator
            or (remainder * 2 == denominator and quotient % 2 == 1)
        )
    )


def _realized_span(step: Mapping[str, Any], gate_scale_q: int) -> tuple[int, int]:
    """The step's realized ``(onset, duration)`` in bar-relative ticks.

    Mirrors the compiler exactly: the onset wraps modulo the bar length and
    the duration is the gate-scaled step duration, rounded half to even and
    clamped to at least one tick.
    """
    onset = step["at_tick"] % _TICKS_PER_BAR
    duration = max(1, _round_half_even(step["duration_ticks"] * gate_scale_q, 10_000))
    return onset, duration


def _span_contains(span: tuple[int, int], note_onset: int, note_duration: int) -> bool:
    """Whether a periodic span contains a note (the compiler's exact rule).

    Both are interpreted on the bar circle (period ``_TICKS_PER_BAR``): the
    compiler's MELODY_HARMONY_CONFLICT check requires
    ``occurrence.start <= note.onset and note.end <= occurrence.start +
    occurrence.duration`` for occurrences in the same section, which across
    bar boundaries is exactly periodic containment.
    """
    start, length = span
    delta = note_onset - start  # in (-L, L)
    # Contained iff an integer bar offset n exists with:
    #   start + n*L <= note_onset            ->  n >= -delta / L
    #   note_onset + note_duration <= start + length + n*L  ->  n <= (length - delta - note_duration) / L
    low = -(delta // _TICKS_PER_BAR)  # ceil(-delta / L)
    high = (length - delta - note_duration) // _TICKS_PER_BAR
    return low <= high


def _spans_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    """Whether two periodic spans overlap (strictly; touching is not overlap)."""
    a_start, a_length = a
    b_start, b_length = b
    delta = b_start - a_start  # in (-L, L)
    # Overlap iff an integer bar offset n exists with:
    #   a_start + n*L < b_start + b_length  ->  n > (delta - a_length) / L
    #   b_start + n*L < a_start + a_length  ->  n < (delta + b_length) / L
    low = (delta - a_length) // _TICKS_PER_BAR + 1
    high = (delta + b_length - 1) // _TICKS_PER_BAR
    return low <= high


def _check_cross_fields(profile: Mapping[str, Any]) -> None:
    """Check the profile's cross-field musical constraints (fail closed).

    These mirror the compiler's contracts for the v3 pipeline, checked early
    with typed codes so a bad profile fails at validation time instead of
    deep in the compile:

    * the v3 harmony cell carries exactly one chord per slot under a zip
      mapping, so a zip rhythm may have at most one step (a cycle rhythm may
      re-strike the single chord on any number of steps);
    * the v3 melody material carries three points under a zip mapping, so the
      melody rhythm may have at most three steps;
    * no two realized harmony occurrences may overlap in time (the compiler's
      MELODY_HARMONY_CONFLICT check requires each melody note to fall inside
      *exactly one* harmony occurrence's span, so two simultaneous chords are
      rejected here);
    * every realized melody note must fall inside exactly one realized harmony
      occurrence's span (the same compiler contract, checked per bar with the
      compiler's exact gate-scaled durations and onset wrapping).

    Passing these checks still does not guarantee a successful compile (see
    the module docstring); generation remains fail-closed.
    """
    harmony = profile["harmony"]
    melody = profile["melody"]
    h_steps = harmony["rhythm"]["steps"]
    m_steps = melody["rhythm"]["steps"]

    if harmony["rhythm"]["mapping"] == "zip" and len(h_steps) != 1:
        raise StyleProfileError(
            "STYLE_PROFILE_HARMONY_ZIP_STEPS_INVALID",
            f"zip requires exactly one step (one chord per slot), got {len(h_steps)}",
        )
    if len(m_steps) > _MELODY_MAX_STEPS:
        raise StyleProfileError(
            "STYLE_PROFILE_MELODY_STEPS_INVALID",
            f"the v3 melody material has {_MELODY_MAX_STEPS} points (zip), "
            f"got {len(m_steps)} steps",
        )

    h_spans = [_realized_span(step, harmony["gate_scale_q"]) for step in h_steps]
    m_spans = [_realized_span(step, melody["gate_scale_q"]) for step in m_steps]

    for i in range(len(h_spans)):
        for j in range(i + 1, len(h_spans)):
            if _spans_overlap(h_spans[i], h_spans[j]):
                raise StyleProfileError(
                    "STYLE_PROFILE_HARMONY_OVERLAP",
                    f"harmony steps {i} and {j} overlap after gate scaling",
                )
    for index, (m_start, m_length) in enumerate(m_spans):
        containing = sum(1 for span in h_spans if _span_contains(span, m_start, m_length))
        if containing == 0:
            raise StyleProfileError(
                "STYLE_PROFILE_MELODY_OUTSIDE_HARMONY",
                f"melody step {index} falls outside every harmony occurrence "
                f"after gate scaling",
            )
        if containing > 1:
            # Defensive: two spans both containing a note overlap, so the
            # check above fires first; kept so this function is correct on its
            # own if the checks are ever reordered.
            raise StyleProfileError(
                "STYLE_PROFILE_MELODY_AMBIGUOUS_HARMONY",
                f"melody step {index} falls inside {containing} overlapping "
                f"harmony occurrences",
            )


def validate_style_profile(profile: Mapping[str, Any]) -> None:
    """Fail closed on a malformed or tampered style profile."""
    required = {
        "schema", "schema_version", "profile_id", "tempo_milli_bpm",
        "harmony", "melody", "cadence", "profile_hash",
    }
    if not isinstance(profile, Mapping) or set(profile) != required:
        raise StyleProfileError("STYLE_PROFILE_FIELDS_INVALID")
    if profile["schema"] != STYLE_PROFILE_SCHEMA:
        raise StyleProfileError("STYLE_PROFILE_SCHEMA_INVALID")
    if profile["schema_version"] != STYLE_PROFILE_VERSION:
        raise StyleProfileError("STYLE_PROFILE_VERSION_UNSUPPORTED")
    if not isinstance(profile["profile_id"], str) or not profile["profile_id"]:
        raise StyleProfileError("STYLE_PROFILE_ID_INVALID")
    _check_int(profile["tempo_milli_bpm"], _TEMPO_MIN, _TEMPO_MAX, "STYLE_PROFILE_TEMPO_INVALID")

    for role in ("harmony", "melody"):
        block = profile[role]
        if not isinstance(block, Mapping):
            raise StyleProfileError("STYLE_PROFILE_ROLE_INVALID", role)
        if set(block) != {"velocity_scale_q", "gate_scale_q", "rhythm"}:
            raise StyleProfileError("STYLE_PROFILE_ROLE_FIELDS_INVALID", role)
        _check_int(block["velocity_scale_q"], _VELOCITY_MIN, _VELOCITY_MAX, "STYLE_PROFILE_VELOCITY_INVALID")
        _check_int(block["gate_scale_q"], _GATE_MIN, _GATE_MAX, "STYLE_PROFILE_GATE_INVALID")
        rhythm = block["rhythm"]
        if not isinstance(rhythm, Mapping):
            raise StyleProfileError("STYLE_PROFILE_RHYTHM_INVALID", role)
        if role == "harmony":
            if set(rhythm) != {"mapping", "steps"}:
                raise StyleProfileError("STYLE_PROFILE_RHYTHM_FIELDS_INVALID", role)
            if rhythm["mapping"] not in ("zip", "cycle"):
                raise StyleProfileError("STYLE_PROFILE_RHYTHM_MAPPING_INVALID", role)
        else:
            if set(rhythm) != {"steps"}:
                raise StyleProfileError("STYLE_PROFILE_RHYTHM_FIELDS_INVALID", role)
        _check_steps(rhythm["steps"], "STYLE_PROFILE_STEPS_INVALID")

    cadence = profile["cadence"]
    if not isinstance(cadence, Mapping) or set(cadence) != {"voice_leading_cap_millicents", "candidate_budget"}:
        raise StyleProfileError("STYLE_PROFILE_CADENCE_FIELDS_INVALID")
    # Integer millicents (strictly positive, at most one octave) keeps the
    # profile body float-free for the canonical artifact encoding.
    cap = cadence["voice_leading_cap_millicents"]
    if type(cap) is not int or isinstance(cap, bool) or not _CADENCE_CAP_MIN < cap <= _CADENCE_CAP_MAX:
        raise StyleProfileError("STYLE_PROFILE_CADENCE_CAP_INVALID", repr(cap))
    _check_int(cadence["candidate_budget"], _CADENCE_BUDGET_MIN, _CADENCE_BUDGET_MAX, "STYLE_PROFILE_CADENCE_BUDGET_INVALID")

    # Cross-field musical constraints (typed codes; see _check_cross_fields).
    _check_cross_fields(profile)

    if style_profile_hash(profile) != profile["profile_hash"]:
        raise StyleProfileError("STYLE_PROFILE_HASH_MISMATCH")


def build_style_profile(
    profile_id: str,
    *,
    tempo_milli_bpm: int,
    harmony_velocity_scale_q: int,
    harmony_gate_scale_q: int,
    harmony_mapping: str,
    harmony_steps: list[dict[str, int]],
    melody_velocity_scale_q: int,
    melody_gate_scale_q: int,
    melody_steps: list[dict[str, int]],
    voice_leading_cap_millicents: int,
    candidate_budget: int,
) -> dict[str, Any]:
    """Assemble a (unsealed) versioned style profile body and stamp its hash."""
    profile = {
        "schema": STYLE_PROFILE_SCHEMA,
        "schema_version": STYLE_PROFILE_VERSION,
        "profile_id": profile_id,
        "tempo_milli_bpm": tempo_milli_bpm,
        "harmony": {
            "velocity_scale_q": harmony_velocity_scale_q,
            "gate_scale_q": harmony_gate_scale_q,
            "rhythm": {"mapping": harmony_mapping, "steps": [dict(step) for step in harmony_steps]},
        },
        "melody": {
            "velocity_scale_q": melody_velocity_scale_q,
            "gate_scale_q": melody_gate_scale_q,
            "rhythm": {"steps": [dict(step) for step in melody_steps]},
        },
        "cadence": {
            "voice_leading_cap_millicents": voice_leading_cap_millicents,
            "candidate_budget": candidate_budget,
        },
        "profile_hash": "",
    }
    profile["profile_hash"] = style_profile_hash(profile)
    validate_style_profile(profile)
    return profile


def _step(at_tick: int, duration_ticks: int, accent_q: int) -> dict[str, int]:
    return {"at_tick": at_tick, "duration_ticks": duration_ticks, "accent_q": accent_q}


# Two built-in, clearly contrasting experimental control configurations.
# The labels are deliberately neutral (restrained / driving); they describe the
# realized tempo / dynamics / rhythm / progression, not an auditory judgement.
# The melody-harmony contract (compiler) requires every melody note to fall
# inside exactly one harmony occurrence's time span, so each profile aligns its
# melody onsets to the harmony onsets and keeps the melody notes shorter than
# the harmony occurrences.  The two profiles are deliberately contrasting:
#
# * ``restrained`` — one sustained harmony chord per bar, slow, soft, the
#   melody spread across the bar (a reflective control).
# * ``driving`` — four staccato harmony re-strikes per bar, fast, loud, the
#   melody clustered on the first three onsets (an energetic control).
STYLE_PROFILES: dict[str, dict[str, Any]] = {
    "restrained": build_style_profile(
        "piano-v3-style-restrained/v1",
        tempo_milli_bpm=72_000,  # 72 BPM — slow
        harmony_velocity_scale_q=4_500,  # soft
        harmony_gate_scale_q=10_000,  # full-bar sustain
        harmony_mapping="zip",
        harmony_steps=[_step(0, 1_920, 4_000)],  # one sustained chord per bar
        melody_velocity_scale_q=5_500,  # soft
        melody_gate_scale_q=8_500,  # sustained
        melody_steps=[
            _step(0, 640, 5_000),
            _step(640, 640, 4_000),
            _step(1_280, 640, 4_000),
        ],
        voice_leading_cap_millicents=250_000,  # tight -> smooth progression
        candidate_budget=16,
    ),
    "driving": build_style_profile(
        "piano-v3-style-driving/v1",
        tempo_milli_bpm=150_000,  # 150 BPM — fast
        harmony_velocity_scale_q=9_000,  # loud
        harmony_gate_scale_q=5_000,  # short staccato
        harmony_mapping="cycle",  # re-strike the chord four times per bar
        harmony_steps=[
            _step(0, 480, 9_000),
            _step(480, 480, 7_000),
            _step(960, 480, 9_000),
            _step(1_440, 480, 7_000),
        ],
        melody_velocity_scale_q=9_500,  # loud
        melody_gate_scale_q=5_000,  # short
        melody_steps=[
            _step(0, 160, 9_500),
            _step(480, 160, 7_000),
            _step(960, 160, 9_500),
        ],
        voice_leading_cap_millicents=800_000,  # loose -> varied progression
        candidate_budget=32,
    ),
}


def load_style_profile(path) -> dict[str, Any]:
    """Read a style profile from a JSON file and validate it (fail closed)."""
    from pathlib import Path

    data = json.loads(Path(path).read_text())
    validate_style_profile(data)
    return data


def apply_style_profile(program: Mapping[str, Any], profile: Mapping[str, Any]) -> dict[str, Any]:
    """Return a clone of ``program`` with the profile's realization applied.

    The sealed harmony dictionary and the cadence plan's dictionary binding are
    untouched: this alters only the clock tempo, the per-role realization
    velocity / gate, the per-role rhythm steps (and the harmony cell's mapping),
    so the realized Program / Project / MIDI change while every chord still
    binds to its sealed variant.  The input is not mutated.
    """
    validate_style_profile(profile)
    result = copy.deepcopy(dict(program))

    # Clock tempo (flows to the Project clock and the MIDI tempo).
    result["clock"]["tempo_milli_bpm"] = profile["tempo_milli_bpm"]

    # Per-role realization velocity / gate, keyed by the track's role.
    role_scales = {
        "harmony": (profile["harmony"]["velocity_scale_q"], profile["harmony"]["gate_scale_q"]),
        "melody": (profile["melody"]["velocity_scale_q"], profile["melody"]["gate_scale_q"]),
    }
    roles_by_track = {track["id"]: track.get("role") for track in result.get("tracks", [])}
    for realization in result.get("realizations", []):
        role = roles_by_track.get(realization.get("track_id"))
        if role in role_scales:
            velocity, gate = role_scales[role]
            realization["velocity_scale_q"] = velocity
            realization["gate_scale_q"] = gate

    # Per-role rhythm steps (and the harmony cell's mapping).
    materials = result.get("materials", [])
    rhythm_ids_by_role: dict[str, set[str]] = {"harmony": set(), "melody": set()}
    for material in materials:
        if material.get("kind") == "harmony_intent_cell":
            rhythm_ids_by_role["harmony"].add(material.get("rhythm_id"))
        elif material.get("kind") == "melody_intent":
            rhythm_ids_by_role["melody"].add(material.get("rhythm_id"))
    # The SongProgram 0.3 rhythmStep schema requires ``lane_id`` (always ``None``
    # in this single-lane pipeline); the profile's steps carry only the musical
    # parameters, so the structural field is injected here.
    def _with_lane(step: Mapping[str, Any]) -> dict[str, Any]:
        return {"at_tick": step["at_tick"], "duration_ticks": step["duration_ticks"],
                "accent_q": step["accent_q"], "lane_id": None}

    for material in materials:
        if material.get("kind") == "rhythm_cell":
            cell_id = material.get("id")
            if cell_id in rhythm_ids_by_role["harmony"]:
                material["steps"] = [_with_lane(step) for step in profile["harmony"]["rhythm"]["steps"]]
            elif cell_id in rhythm_ids_by_role["melody"]:
                material["steps"] = [_with_lane(step) for step in profile["melody"]["rhythm"]["steps"]]
    for material in materials:
        if material.get("kind") == "harmony_intent_cell":
            material["mapping"] = profile["harmony"]["rhythm"]["mapping"]

    return result
