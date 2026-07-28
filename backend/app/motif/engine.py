"""7-limit motif generation, variation, and comparison helpers."""

from __future__ import annotations

from fractions import Fraction
from math import exp, log2
from random import Random
from typing import Any

from app.tuning.analysis import cents, monzo
from app.tuning.ratios import ratio_text, reduce_to_octave

PRIMES = (2, 3, 5, 7)
WEIGHTS = (0.0, 1.0, 1.25, 1.55)
PROFILE_WEIGHTS = {
    "balanced": {"harmony": 0.30, "melody": 0.25, "rhythm": 0.25, "identity": 0.10, "novelty": 0.10},
    "consonant": {"harmony": 0.48, "melody": 0.22, "rhythm": 0.12, "identity": 0.12, "novelty": 0.06},
    "lyrical": {"harmony": 0.25, "melody": 0.42, "rhythm": 0.15, "identity": 0.12, "novelty": 0.06},
    "rhythmic": {"harmony": 0.20, "melody": 0.18, "rhythm": 0.43, "identity": 0.10, "novelty": 0.09},
    "colourful": {"harmony": 0.20, "melody": 0.24, "rhythm": 0.18, "identity": 0.14, "novelty": 0.24},
}
AFFINITY_FLOORS = {"balanced": 0.20, "consonant": 0.30, "lyrical": 0.18, "rhythmic": 0.16, "colourful": 0.12}
ANCHOR_ROLES = ("root", "third", "fifth", "colour")


def fixed_monzo(ratio: Fraction) -> tuple[int, int, int, int]:
    """Return a 7-limit monzo in the stable [2, 3, 5, 7] order."""
    sparse = {int(prime): exponent for prime, exponent in monzo(ratio).items()}
    unsupported = set(sparse) - set(PRIMES)
    if unsupported:
        raise ValueError("motif ratios must use primes no greater than 7")
    return tuple(sparse.get(prime, 0) for prime in PRIMES)  # type: ignore[return-value]


def circle_cent(ratio: Fraction) -> float:
    return cents(reduce_to_octave(ratio))


def signed_circle_delta(left: float, right: float) -> float:
    """Shortest signed movement from left to right in [-600, 600)."""
    return (right - left + 600) % 1200 - 600


def monzo_distance(left: tuple[int, ...], right: tuple[int, ...]) -> float:
    return sum(weight * abs(a - b) for weight, a, b in zip(WEIGHTS, left, right))


def _midi_number(ratio: Fraction, base_frequency: int = 220) -> float:
    return 69 + cents(ratio * Fraction(base_frequency, 440)) / 100


def _place_in_register(ratio: Fraction, low: int, high: int) -> Fraction | None:
    candidate = ratio
    while _midi_number(candidate) < low:
        candidate *= 2
    while _midi_number(candidate / 2) >= low:
        candidate /= 2
    return candidate if _midi_number(candidate) <= high else None


def _pitch_payload(ratio: Fraction, onset: float, duration: float, relation: str, velocity: int = 92) -> dict[str, Any]:
    vector = fixed_monzo(ratio)
    return {
        "ratio": ratio_text(ratio),
        "monzo": list(vector),
        "pitch_circle_cent": round(circle_cent(ratio), 5),
        "register_cent": round(cents(ratio), 5),
        "onset_beat": round(onset, 5),
        "duration_beats": round(duration, 5),
        "velocity": velocity,
        "accent": False,
        "chord_relation": relation,
    }


def _canonical_notes(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    canonical = []
    for note in notes:
        payload = _pitch_payload(
            Fraction(note["ratio"]),
            float(note["onset_beat"]),
            float(note["duration_beats"]),
            str(note.get("chord_relation", "exact")),
            int(note.get("velocity", 92)),
        )
        payload["accent"] = bool(note.get("accent", False))
        canonical.append(payload)
    return canonical


def _relation(ratio: Fraction, anchors: list[Fraction]) -> str:
    candidate = fixed_monzo(reduce_to_octave(ratio))
    distance = min(monzo_distance(candidate, fixed_monzo(reduce_to_octave(anchor))) for anchor in anchors)
    if distance == 0:
        return "exact"
    if distance <= 1.55:
        return "near"
    if distance <= 3.8:
        return "related"
    return "contrast"


def _relation_rank(value: str) -> int:
    return {"exact": 0, "near": 1, "related": 2, "contrast": 3}[value]


def _candidate_pool(anchors: list[Fraction], low: int, high: int, radius: int) -> list[dict[str, Any]]:
    candidates: dict[Fraction, dict[str, Any]] = {}
    for anchor in anchors:
        for p3 in range(-radius, radius + 1):
            for p5 in range(-radius, radius + 1):
                for p7 in range(-radius, radius + 1):
                    if abs(p3) + abs(p5) + abs(p7) > radius:
                        continue
                    ratio = anchor * Fraction(3) ** p3 * Fraction(5) ** p5 * Fraction(7) ** p7
                    placed = _place_in_register(ratio, low, high)
                    if placed is None:
                        continue
                    relation = _relation(placed, anchors)
                    existing = candidates.get(placed)
                    if existing is None or _relation_rank(relation) < _relation_rank(existing["relation"]):
                        candidates[placed] = {"ratio": placed, "relation": relation}
    return [candidates[key] for key in sorted(candidates)]


def _rhythm(note_count: int, length_beats: float, profile: str, random: Random) -> list[tuple[float, float]]:
    if profile == "random_exploration":
        total_steps = round(length_beats * 16)
        minimum_steps = 2 if total_steps >= note_count * 2 else 1
        durations = [minimum_steps] * note_count
        for _ in range(total_steps - minimum_steps * note_count):
            durations[random.randrange(note_count)] += 1
        random_onsets: list[tuple[float, float]] = []
        cursor = 0
        for duration in durations:
            random_onsets.append((cursor / 16, duration / 16))
            cursor += duration
        return random_onsets
    if profile == "kawaii_syncopated" and note_count >= 4:
        grid = [0, 0.75, 1.25, 1.75, 2.5, 3.0, 3.5, 3.75]
        template_onsets = [value * length_beats / 4 for value in grid[:note_count]]
    else:
        template_onsets = [index * length_beats / note_count for index in range(note_count)]
    return [(onset, max(0.125, (template_onsets[index + 1] if index + 1 < note_count else length_beats) - onset)) for index, onset in enumerate(template_onsets)]


def _affinity(ratio: Fraction, anchors: list[Fraction]) -> float:
    candidate = fixed_monzo(reduce_to_octave(ratio))
    value = 0.0
    for anchor in anchors:
        anchor_vector = fixed_monzo(reduce_to_octave(anchor))
        monzo_term = monzo_distance(candidate, anchor_vector)
        circle = abs(signed_circle_delta(circle_cent(ratio), circle_cent(anchor))) / 600
        value = max(value, exp(-(monzo_term**2) / 4 - (circle**2) / 0.35))
    return value


def signature(notes: list[dict[str, Any]], anchors: list[Fraction]) -> dict[str, Any]:
    intervals = []
    for left, right in zip(notes, notes[1:]):
        left_ratio, right_ratio = Fraction(left["ratio"]), Fraction(right["ratio"])
        intervals.append({
            "monzo_delta": [b - a for a, b in zip(left["monzo"], right["monzo"])],
            "circle_delta_cent": round(signed_circle_delta(left["pitch_circle_cent"], right["pitch_circle_cent"]), 5),
            "register_delta_cent": round(cents(right_ratio / left_ratio), 5),
            "duration_ratio": round(right["duration_beats"] / left["duration_beats"], 5),
        })
    longest = max(range(len(notes)), key=lambda index: notes[index]["duration_beats"])
    peak = max(range(len(notes)), key=lambda index: notes[index]["register_cent"])
    return {
        "interval_signature": intervals,
        "rhythm_signature": {
            "onsets": [note["onset_beat"] for note in notes],
            "durations": [note["duration_beats"] for note in notes],
            "accents": [note["accent"] for note in notes],
        },
        "contour_signature": [
            0 if interval["register_delta_cent"] == 0 else (1 if interval["register_delta_cent"] > 0 else -1)
            for interval in intervals
        ],
        "anchor_membership": {key: sum(note["chord_relation"] == key for note in notes) / len(notes) for key in ("exact", "near", "related", "contrast")},
        "chord_affinity": round(sum(_affinity(Fraction(note["ratio"]), anchors) for note in notes) / len(notes), 5),
        "identity_features": {
            "opening_intervals": intervals[:2],
            "highest_note_index": peak,
            "longest_note_index": longest,
            "terminal_relation": notes[-1]["chord_relation"],
            "terminal_role": notes[-1].get("terminal_role"),
            "has_7_limit_colour": any(note["monzo"][3] != 0 for note in notes),
        },
    }


def _score_candidate(candidate: dict[str, Any], previous: dict[str, Any] | None, anchors: list[Fraction], profile: str) -> float:
    relation_bonus = {"exact": 1.0, "near": 0.78, "related": 0.45, "contrast": 0.12}[candidate["relation"]]
    if previous is None:
        return relation_bonus + _affinity(candidate["ratio"], anchors)
    circle = abs(signed_circle_delta(circle_cent(Fraction(previous["ratio"])), circle_cent(candidate["ratio"])))
    desired = 0.8 if profile == "mostly_stepwise" and 100 <= circle <= 350 else 0.35
    leap = abs(cents(candidate["ratio"] / Fraction(previous["ratio"])))
    return relation_bonus + desired + _affinity(candidate["ratio"], anchors) - max(0, leap - 700) / 700


def _terminal_anchor_candidates(anchors: list[Fraction], low: int, high: int) -> list[dict[str, Any]]:
    candidates = []
    for index, anchor in enumerate(anchors):
        placed = _place_in_register(anchor, low, high)
        if placed is not None:
            candidates.append({"ratio": placed, "role": ANCHOR_ROLES[index]})
    if not candidates:
        raise ValueError("anchor chord has no legal terminal tone in the requested register")
    return candidates


def _choose_terminal(
    policy: str, candidates: list[dict[str, Any]], previous: Fraction, random: Random
) -> dict[str, Any] | None:
    if policy == "free":
        return None
    by_role = {candidate["role"]: candidate for candidate in candidates}
    if policy == "root":
        return by_role.get("root", candidates[0])
    if policy == "stable":
        stable = [candidate for candidate in candidates if candidate["role"] in {"root", "fifth"}]
        return stable[random.randrange(len(stable))] if stable else candidates[0]
    if policy == "colour":
        colour = [candidate for candidate in candidates if candidate["role"] in {"third", "colour"}]
        return colour[random.randrange(len(colour))] if colour else candidates[-1]
    if policy == "nearest_anchor":
        return min(candidates, key=lambda candidate: abs(cents(candidate["ratio"] / previous)))
    if policy == "weighted":
        weights = {"root": 0.45, "fifth": 0.30, "third": 0.18, "colour": 0.07}
        return random.choices(candidates, weights=[weights[candidate["role"]] for candidate in candidates])[0]
    return candidates[random.randrange(len(candidates))]


def _generate_one(config: dict[str, Any]) -> dict[str, Any]:
    anchors = [Fraction(value) for value in config["anchor_chord"]]
    low, high = config["register_midi"]
    pool = _candidate_pool(anchors, low, high, config["max_lattice_radius"])
    if len(pool) < config["note_count"]:
        raise ValueError("anchor chord and register do not provide enough motif candidates")
    random = Random(config["seed"])
    notes: list[dict[str, Any]] = []
    for index, (onset, duration) in enumerate(_rhythm(config["note_count"], config["length_beats"], config["rhythm_profile"], random)):
        ranked = sorted(pool, key=lambda item: _score_candidate(item, notes[-1] if notes else None, anchors, config["circle_profile"]), reverse=True)
        width = min(config["beam_width"], len(ranked))
        pick = ranked[random.randrange(width)]
        note = _pitch_payload(pick["ratio"], onset, duration, pick["relation"], 104 if index == 0 else 88)
        note["accent"] = index == 0 or onset.is_integer()
        notes.append(note)
    terminal = _choose_terminal(
        str(config["terminal_policy"]),
        _terminal_anchor_candidates(anchors, low, high),
        Fraction(notes[-1]["ratio"]),
        random,
    )
    if terminal is not None:
        notes[-1] = _pitch_payload(terminal["ratio"], notes[-1]["onset_beat"], notes[-1]["duration_beats"], "exact", 98)
        notes[-1]["terminal_role"] = terminal["role"]
    else:
        notes[-1]["terminal_role"] = "free"
    details = signature(notes, anchors)
    return {
        "id": f"motif-{config['seed']}",
        "seed": config["seed"],
        "engine_version": "0.1",
        "anchor_chord": [ratio_text(ratio) for ratio in anchors],
        "terminal_policy": config["terminal_policy"],
        "notes": notes,
        "candidate_pool_size": len(pool),
        **details,
        "evaluation": {},
    }


def _entropy(values: list[float]) -> float:
    total = sum(values)
    if total <= 0 or len(values) <= 1:
        return 0.0
    probabilities = [value / total for value in values if value]
    return -sum(value * log2(value) for value in probabilities) / log2(len(values))


def _novelty(candidate: dict[str, Any], others: list[dict[str, Any]]) -> float:
    if not others:
        return 1.0
    distances = []
    for other in others:
        pitch = sum(
            abs(signed_circle_delta(left["pitch_circle_cent"], right["pitch_circle_cent"])) / 600
            for left, right in zip(candidate["notes"], other["notes"])
        ) / len(candidate["notes"])
        rhythm = sum(
            abs(left["duration_beats"] - right["duration_beats"])
            for left, right in zip(candidate["notes"], other["notes"])
        ) / max(0.125, sum(note["duration_beats"] for note in candidate["notes"]))
        distances.append(min(1.0, pitch * 0.7 + rhythm * 0.3))
    return round(min(distances), 5)


def _evaluate(candidate: dict[str, Any], profile: str, novelty: float) -> dict[str, Any]:
    notes, intervals = candidate["notes"], candidate["interval_signature"]
    membership = candidate["anchor_membership"]
    affinity = float(candidate["chord_affinity"])
    harmony = min(1.0, affinity * 0.65 + (membership["exact"] + membership["near"]) * 0.25 + (0.10 if notes[-1]["chord_relation"] == "exact" else 0.0))
    circle_steps = [abs(interval["circle_delta_cent"]) for interval in intervals]
    stepwise = sum(80 <= value <= 360 for value in circle_steps) / max(1, len(circle_steps))
    directions = candidate["contour_signature"]
    turns = sum(left != right for left, right in zip(directions, directions[1:]))
    melody = min(1.0, stepwise * 0.7 + max(0.0, 1 - turns / max(1, len(directions))) * 0.3)
    durations = [float(note["duration_beats"]) for note in notes]
    duration_ratio = max(durations) / min(durations)
    syncopation = sum(not float(note["onset_beat"]).is_integer() for note in notes) / len(notes)
    rhythm = min(1.0, _entropy(durations) * 0.55 + min(1.0, syncopation * 2) * 0.25 + min(1.0, duration_ratio / 3) * 0.20)
    identity = (0.55 if notes[-1]["chord_relation"] == "exact" else 0.0) + (0.25 if any(interval["circle_delta_cent"] != 0 for interval in intervals[:2]) else 0.0) + (0.20 if candidate["identity_features"]["has_7_limit_colour"] else 0.0)
    complexity = min(1.0, sum(sum(abs(value) for value in note["monzo"][1:]) for note in notes) / (len(notes) * 7))
    components = {"harmony": round(harmony, 5), "melody": round(melody, 5), "rhythm": round(rhythm, 5), "identity": round(identity, 5), "novelty": novelty, "complexity": round(complexity, 5)}
    total = sum(PROFILE_WEIGHTS[profile][key] * components[key] for key in PROFILE_WEIGHTS[profile]) - complexity * 0.12
    max_leap = max((abs(interval["register_delta_cent"]) for interval in intervals), default=0)
    reasons = []
    if affinity < AFFINITY_FLOORS[profile]:
        reasons.append("anchor affinity below profile floor")
    if membership["exact"] + membership["near"] < 0.34:
        reasons.append("too few anchor or near-anchor tones")
    if max_leap > 1200:
        reasons.append("register leap exceeds one octave")
    if duration_ratio > 6:
        reasons.append("duration contrast is too extreme")
    diagnostics = [
        f"anchor affinity {affinity:.2f}",
        f"stepwise share {stepwise:.2f}",
        f"duration entropy {_entropy(durations):.2f}",
        *reasons,
    ]
    return {"profile": profile, "components": components, "total": round(total, 5), "passed_filters": not reasons, "rejected_reasons": reasons, "diagnostics": diagnostics, "max_register_leap_cents": round(max_leap, 5)}


def generate(config: dict[str, Any]) -> dict[str, Any]:
    count = int(config["candidate_count"])
    candidates = [_generate_one({**config, "seed": int(config["seed"]) + index}) for index in range(count)]
    profile = str(config["evaluation_profile"])
    for index, candidate in enumerate(candidates):
        candidate["evaluation"] = _evaluate(candidate, profile, _novelty(candidate, candidates[:index]))
    passing = [candidate for candidate in candidates if candidate["evaluation"]["passed_filters"]]
    rejected = [candidate for candidate in candidates if not candidate["evaluation"]["passed_filters"]]
    ranked = sorted(passing, key=lambda candidate: candidate["evaluation"]["total"], reverse=True) + sorted(
        rejected, key=lambda candidate: candidate["evaluation"]["total"], reverse=True
    )
    for rank, candidate in enumerate(ranked, start=1):
        candidate["evaluation"]["rank"] = rank
    best = dict(ranked[0])
    best["candidates"] = ranked
    best["exploration"] = {"requested": count, "accepted": len(passing), "rejected": count - len(passing), "profile": profile}
    return best


def _distance(source: list[dict[str, Any]], target: list[dict[str, Any]], anchors: list[Fraction]) -> dict[str, float]:
    length = max(len(source), len(target))
    paired = list(zip(source, target))
    if not paired:
        raise ValueError("motifs must contain notes")
    absolute = sum(monzo_distance(tuple(a["monzo"]), tuple(b["monzo"])) for a, b in paired) / len(paired)
    circle = sum(abs(signed_circle_delta(a["pitch_circle_cent"], b["pitch_circle_cent"])) / 600 for a, b in paired) / len(paired)
    register = sum(abs(a["register_cent"] - b["register_cent"]) / 1200 for a, b in paired) / len(paired)
    rhythm = sum(abs(a["onset_beat"] - b["onset_beat"]) + abs(a["duration_beats"] - b["duration_beats"]) for a, b in paired) / len(paired)
    source_signature, target_signature = signature(source, anchors), signature(target, anchors)
    shape = sum(
        sum(abs(x - y) for x, y in zip(a["monzo_delta"], b["monzo_delta"]))
        for a, b in zip(source_signature["interval_signature"], target_signature["interval_signature"])
    ) / max(1, len(source_signature["interval_signature"]))
    contour = sum(a != b for a, b in zip(source_signature["contour_signature"], target_signature["contour_signature"])) / max(1, len(source_signature["contour_signature"]))
    return {
        "absolute_monzo": round(absolute, 5),
        "relative_monzo_shape": round(shape, 5),
        "pitch_circle": round(circle, 5),
        "register": round(register, 5),
        "contour": round(contour, 5),
        "rhythm": round(rhythm, 5),
        "chord_affinity_change": round(target_signature["chord_affinity"] - source_signature["chord_affinity"], 5),
        "length_delta": abs(len(source) - len(target)) / length,
    }


def compare(source: list[dict[str, Any]], target: list[dict[str, Any]], anchors: list[Fraction]) -> dict[str, Any]:
    source, target = _canonical_notes(source), _canonical_notes(target)
    vector = _distance(source, target, anchors)
    identity = max(0.0, 1 - (vector["relative_monzo_shape"] * 0.18 + vector["pitch_circle"] * 0.3 + vector["rhythm"] * 0.2 + vector["contour"] * 0.2))
    return {
        "distance_vector": vector,
        "identity_retention": round(identity, 5),
        "alignment": [{"source_index": index, "target_index": index} for index in range(min(len(source), len(target)))],
        "recognized_transformations": [],
    }


def vary(config: dict[str, Any]) -> dict[str, Any]:
    source = _canonical_notes(config["source_notes"])
    anchors = [Fraction(value) for value in config["anchor_chord"]]
    target = [Fraction(value) for value in config["target_chord"]]
    random = Random(config["seed"])
    transformations = config["allowed_transformations"]
    notes = [dict(note) for note in source]
    chain: list[str] = []
    if "retrograde_pitch" in transformations:
        ratios = [note["ratio"] for note in reversed(notes)]
        for note, ratio in zip(notes, ratios):
            note.update(_pitch_payload(Fraction(ratio), note["onset_beat"], note["duration_beats"], note["chord_relation"], note["velocity"]))
        chain.append("retrograde_pitch")
    if "lattice_transpose" in transformations:
        factor = Fraction(3, 2) if random.randrange(2) else Fraction(5, 4)
        for note in notes:
            ratio = Fraction(note["ratio"]) * factor
            note.update(_pitch_payload(ratio, note["onset_beat"], note["duration_beats"], _relation(ratio, target), note["velocity"]))
        chain.append("lattice_transpose")
    if "neighbour_substitution" in transformations:
        for index in range(1, len(notes), 2):
            ratio = Fraction(notes[index]["ratio"]) * Fraction(7, 6)
            note = notes[index]
            note.update(_pitch_payload(ratio, note["onset_beat"], note["duration_beats"], _relation(ratio, target), note["velocity"]))
        chain.append("neighbour_substitution")
    if "rhythmic_diminution" in transformations:
        for note in notes:
            note["duration_beats"] = round(max(0.125, note["duration_beats"] * 0.5), 5)
        chain.append("rhythmic_diminution")
    if "chord_tone_projection" in transformations:
        for index, note in enumerate(notes):
            if index % 2:
                candidate = target[index % len(target)]
                note.update(_pitch_payload(candidate, note["onset_beat"], note["duration_beats"], "exact", note["velocity"]))
        chain.append("chord_tone_projection")
    details = signature(notes, target)
    comparison = compare(source, notes, anchors)
    return {
        "id": f"variation-{config['seed']}",
        "source_motif_id": config.get("source_motif_id", "inline-motif"),
        "target_chord": [ratio_text(ratio) for ratio in target],
        "formal_role": config["formal_role"],
        "transformation_chain": chain,
        "notes": notes,
        **details,
        **comparison,
        "current_chord_affinity": details["chord_affinity"],
        "evaluation": {"total": comparison["identity_retention"], "diagnostics": []},
    }


def develop(config: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic section-scale motif tree from an inline theme."""
    source = _canonical_notes(config["source_notes"])
    anchors = [Fraction(value) for value in config["anchor_chord"]]
    duration = max(note["onset_beat"] + note["duration_beats"] for note in source)
    roles = config["section_roles"] or ["theme", "a_prime", "development", "recapitulation"]
    variants: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    role_transforms = {
        "theme": [],
        "a_prime": ["neighbour_substitution"],
        "build": ["rhythmic_diminution"],
        "development": ["lattice_transpose", "neighbour_substitution"],
        "climax": ["chord_tone_projection", "lattice_transpose"],
        "recapitulation": [],
        "coda": ["rhythmic_diminution"],
    }
    for index, role in enumerate(roles):
        target = config["harmony"][index % len(config["harmony"])]
        if role in {"theme", "recapitulation"}:
            notes = _canonical_notes(source)
            item = {
                "id": f"motif-section-{index}",
                "source_motif_id": "motif-original",
                "formal_role": role,
                "target_chord": target,
                "transformation_chain": [],
                "notes": notes,
                **signature(notes, [Fraction(value) for value in target]),
                **compare(source, notes, anchors),
            }
        else:
            item = vary({
                "source_notes": source,
                "anchor_chord": config["anchor_chord"],
                "target_chord": target,
                "source_motif_id": "motif-original",
                "formal_role": role,
                "allowed_transformations": role_transforms[role],
                "seed": config["seed"] + index,
            })
        offset = index * duration * 2
        for note in item["notes"]:
            events.append({
                "ratio": note["ratio"],
                "start_beats": round(offset + note["onset_beat"], 5),
                "duration_beats": note["duration_beats"],
                "velocity": note["velocity"],
                "section_index": index,
                "formal_role": role,
            })
        variants.append(item)
        if index:
            edges.append({
                "source": variants[index - 1]["id"],
                "target": item["id"],
                "transformations": item["transformation_chain"],
                "distance_vector": item["distance_vector"],
            })
    return {
        "seed": config["seed"],
        "anchor_chord": [ratio_text(ratio) for ratio in anchors],
        "motif_tree": {"root": "motif-original", "nodes": variants, "edges": edges},
        "sections": [
            {"index": index, "role": role, "motif_id": item["id"], "start_beat": round(index * duration * 2, 5)}
            for index, (role, item) in enumerate(zip(roles, variants, strict=True))
        ],
        "events": events,
    }
