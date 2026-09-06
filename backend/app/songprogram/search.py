"""Deterministic GEN0-D search-artifact primitives.

This module deliberately has no dependency on ``songprogram_conformance``:
that package is the independent oracle used by the tests.
"""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import struct
import tempfile
import unicodedata
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Sequence


class SearchArtifactError(ValueError):
    """A stable GEN0-D artifact error."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _nfc(value: Any) -> Any:
    if isinstance(value, str):
        if unicodedata.normalize("NFC", value) != value:
            raise SearchArtifactError("CANONICAL_STRING_NOT_NFC")
        return value
    if isinstance(value, list):
        return [_nfc(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise SearchArtifactError("CANONICAL_OBJECT_KEY_INVALID")
        return {key: _nfc(item) for key, item in value.items()}
    if isinstance(value, (type(None), bool, int)):
        return value
    raise SearchArtifactError("CANONICAL_VALUE_INVALID")


def canonical_bytes(value: Any) -> bytes:
    """Return CPS canonical JSON bytes for GEN0-D artifacts, including its LF."""
    return (json.dumps(_nfc(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def manifest_digest(domain: str, value: Any) -> str:
    return sha256_digest(domain.encode("utf-8") + b"\0" + canonical_bytes(value))


def _round_half_even(value: Fraction) -> int:
    quotient, remainder = divmod(value.numerator, value.denominator)
    doubled = remainder * 2
    if doubled < value.denominator:
        return quotient
    if doubled > value.denominator:
        return quotient + 1
    return quotient + (quotient & 1)


def descriptor_values(
    contributions: Sequence[int], lineage_pair_distances_q: Sequence[int]
) -> tuple[int | None, int | None]:
    """Aggregate already-normalized descriptor observations per DescriptorSpec v1."""
    if any(not 0 <= value <= 5 for value in contributions):
        raise SearchArtifactError("DESCRIPTOR_CONTRIBUTION_INVALID")
    if any(not 0 <= value <= 10_000 for value in lineage_pair_distances_q):
        raise SearchArtifactError("DESCRIPTOR_DISTANCE_INVALID")
    syncopation = (
        None
        if not contributions
        else _round_half_even(Fraction(10_000 * sum(contributions), 5 * len(contributions)))
    )
    ordered = sorted(lineage_pair_distances_q)
    if not ordered:
        recurrence = None
    elif len(ordered) % 2:
        recurrence = ordered[len(ordered) // 2]
    else:
        midpoint = len(ordered) // 2
        recurrence = _round_half_even(Fraction(ordered[midpoint - 1] + ordered[midpoint], 2))
    return syncopation, recurrence


def _quantized_tick(value: int, quantum: int, tolerance: int) -> int:
    slot = _round_half_even(Fraction(value, quantum))
    if abs(value - slot * quantum) > tolerance:
        raise SearchArtifactError("DESCRIPTOR_UNQUANTIZABLE")
    return slot


def _metrical_strength(slot: int, slots_per_beat: int, beats_per_bar: int) -> int:
    position = slot % slots_per_beat
    base = (3, 0, 1, 0)[position]
    beat = (slot // slots_per_beat) % beats_per_bar
    return base + (2 if beat == 0 else 1)


def _multiset_distance_q(left: list[bytes], right: list[bytes]) -> int:
    left_counts, right_counts = Counter(left), Counter(right)
    keys = left_counts.keys() | right_counts.keys()
    union = sum(max(left_counts[key], right_counts[key]) for key in keys)
    intersection = sum(min(left_counts[key], right_counts[key]) for key in keys)
    return 0 if union == 0 else _round_half_even(Fraction(10_000 * (union - intersection), union))


def descriptor_result_from_project(
    project: dict[str, Any], lineage_index: dict[str, Any], spec: dict[str, Any]
) -> dict[str, Any]:
    """Compute DescriptorResult v1 from canonical Project and LineageIndex inputs."""
    project_hash = sha256_digest(
        project["compiler"]["build_id"].encode("utf-8")
        + b"\0project/1.2.0\0"
        + canonical_bytes(project)[:-1]
    )
    if lineage_index.get("project_hash") != project_hash:
        raise SearchArtifactError("LINEAGE_PROJECT_MISMATCH")
    instances = {item["id"]: item for item in project["material_instances"]}
    lineage_records = {item["material_instance_id"]: item for item in lineage_index["instances"]}
    if set(instances) != set(lineage_records) or len(lineage_records) != len(lineage_index["instances"]):
        raise SearchArtifactError("LINEAGE_INSTANCE_SET_MISMATCH")
    tracks = {item["id"]: item for item in project["tracks"]}
    quantum = spec["quantization_ticks"]
    tolerance = spec["maximum_quantization_error_ticks"]
    slots_per_beat = project["clock"]["ticks_per_beat"] // quantum
    if slots_per_beat != 4:
        raise SearchArtifactError("DESCRIPTOR_CLOCK_UNSUPPORTED")
    contributions = []
    unique_events: dict[bytes, dict[str, Any]] = {}
    for event in project["events"]:
        core = {key: value for key, value in event.items() if key not in {"id", "velocity"}}
        core["source"] = {key: value for key, value in event["source"].items() if key != "semantic_address"}
        unique_events.setdefault(canonical_bytes(core), event)
    for event in unique_events.values():
        role = tracks[event["track_id"]]["role"]
        if not (event["kind"] == "drum" and spec["drums_are_foreground"] or event["kind"] == "note" and role in spec["foreground_roles"]):
            continue
        onset = _quantized_tick(event["start_tick"], quantum, tolerance)
        end = _quantized_tick(event["start_tick"] + event["duration_ticks"], quantum, tolerance)
        next_slot = onset + 1
        if end <= next_slot:
            continue
        contribution = max(0, _metrical_strength(next_slot, slots_per_beat, project["clock"]["beats_per_bar"]) - _metrical_strength(onset, slots_per_beat, project["clock"]["beats_per_bar"]))
        contributions.append(contribution)
    by_instance: dict[str, list[bytes]] = {instance_id: [] for instance_id in instances}
    for event in unique_events.values():
        if event["duration_ticks"] < spec["minimum_recurrence_event_ticks"]:
            continue
        instance = instances[event["source"]["material_instance_id"]]
        onset = _quantized_tick(event["start_tick"] - instance["at_tick"], quantum, tolerance)
        duration = _quantized_tick(event["duration_ticks"], quantum, tolerance)
        if event["kind"] == "drum":
            ratio_pair = [0, 1]
        else:
            ratio = Fraction(event["ratio"])
            equave = Fraction(project["lattice"]["equave"])
            while ratio >= equave:
                ratio /= equave
            while ratio < 1:
                ratio *= equave
            ratio_pair = [ratio.numerator, ratio.denominator]
        payload = [event["kind"], onset, duration, *ratio_pair, event["source"]["source_step_ordinal"]]
        by_instance[instance["id"]].append(canonical_bytes(payload))
    pairs = []
    ordered_instances = sorted(instances.values(), key=lambda item: item["id"].encode())
    for left_index, left in enumerate(ordered_instances):
        for right in ordered_instances[left_index + 1 :]:
            if not by_instance[left["id"]] or not by_instance[right["id"]] or left["section_id"] == right["section_id"] or lineage_records[left["id"]]["lineage_hash"] != lineage_records[right["id"]]["lineage_hash"]:
                continue
            pairs.append(_multiset_distance_q(by_instance[left["id"]], by_instance[right["id"]]))
    syncopation, recurrence = descriptor_values(contributions, pairs)
    return {
        "schema": "cps.descriptor-result",
        "schema_version": "1.0.0",
        "descriptor_spec_hash": manifest_digest("cps.descriptor-spec/v1", spec),
        "project_hash": project_hash,
        "lineage_index_hash": manifest_digest("cps.lineage-index/v1", lineage_index),
        "rhythmic_syncopation_q": syncopation,
        "material_recurrence_distance_q": recurrence,
        "eligible_syncopation_events": len(contributions),
        "recurrence_pair_count": len(pairs),
    }


def fingerprint_component_hash(component_id: str, payload: Any) -> str:
    return manifest_digest(
        "cps.fingerprint-component/v1", {"id": component_id, "payload": payload}
    )


def musical_fingerprint_hash(component_hashes: Sequence[str]) -> str:
    return manifest_digest("cps.musical-fingerprint/v1", list(component_hashes))


def fingerprint_record(
    spec: dict[str, Any],
    payloads: dict[str, Any],
    project_hash: str,
    lineage_index_hash: str,
) -> dict[str, Any]:
    spec_hash = manifest_digest("cps.fingerprint-spec/v1", spec)
    components = []
    for component in spec["components"]:
        component_id = component["id"]
        if component_id not in payloads:
            raise SearchArtifactError("FINGERPRINT_COMPONENT_MISSING")
        components.append(
            {"id": component_id, "hash": fingerprint_component_hash(component_id, payloads[component_id])}
        )
    if set(payloads) != {item["id"] for item in components}:
        raise SearchArtifactError("FINGERPRINT_COMPONENT_EXTRA")
    hashes = [item["hash"] for item in components]
    return {
        "schema": "cps.fingerprint-record",
        "schema_version": "1.0.0",
        "fingerprint_spec_hash": spec_hash,
        "project_hash": project_hash,
        "lineage_index_hash": lineage_index_hash,
        "component_hashes": components,
        "fingerprint_hash": musical_fingerprint_hash(hashes),
    }


def fingerprint_payloads_from_project(
    project: dict[str, Any], lineage_index: dict[str, Any], spec: dict[str, Any]
) -> dict[str, Any]:
    """Extract the six canonical musical fingerprint component payloads."""
    quantum = spec["time_quantization_ticks"]
    tracks = {track["id"]: track for track in project["tracks"]}
    instances = {item["material_instance_id"]: item for item in lineage_index["instances"]}
    if set(instances) != {item["id"] for item in project["material_instances"]}:
        raise SearchArtifactError("LINEAGE_INSTANCE_SET_MISMATCH")
    unique: dict[bytes, dict[str, Any]] = {}
    for event in project["events"]:
        musical = {
            "kind": event["kind"],
            "role": tracks[event["track_id"]]["role"],
            "start_tick": event["start_tick"],
            "duration_ticks": event["duration_ticks"],
            "drum_note": event["drum_note"],
            "ratio": event["ratio"],
        }
        unique.setdefault(canonical_bytes(musical), event)
    events = list(unique.values())
    role_grid = sorted(
        [
            [
                tracks[event["track_id"]]["role"],
                _round_half_even(Fraction(event["start_tick"], quantum)),
                _round_half_even(Fraction(event["duration_ticks"], quantum)),
            ]
            for event in events
        ],
        key=canonical_bytes,
    )
    chords = {chord["id"]: chord for chord in project["resolved_chords"]}
    occurrence_chords = [chords[item["resolved_chord_id"]] for item in project["harmony_occurrences"]]
    if occurrence_chords:
        origin = occurrence_chords[0]["anchor_vector"]
        anchor_deltas = [
            [coordinate - base for coordinate, base in zip(chord["anchor_vector"], origin, strict=True)]
            for chord in occurrence_chords
        ]
    else:
        anchor_deltas = []
    chord_steps = [chord["canonical_steps"] for chord in occurrence_chords]
    lineage_edges = sorted(
        [
            [
                instances[edge["from_instance_id"]]["lineage_hash"],
                instances[edge["to_instance_id"]]["lineage_hash"],
                edge["operation"],
            ]
            for edge in lineage_index["transform_edges"]
        ],
        key=canonical_bytes,
    )
    equave = Fraction(project["lattice"]["equave"])
    pitched = [event for event in events if event["kind"] == "note"]
    intervals = []
    for left_index, left in enumerate(pitched):
        for right in pitched[left_index + 1 :]:
            if max(left["start_tick"], right["start_tick"]) >= min(left["start_tick"] + left["duration_ticks"], right["start_tick"] + right["duration_ticks"]):
                continue
            left_ratio, right_ratio = Fraction(left["ratio"]), Fraction(right["ratio"])
            interval = max(left_ratio, right_ratio) / min(left_ratio, right_ratio)
            while interval >= equave:
                interval /= equave
            while interval < 1:
                interval *= equave
            intervals.append(f"{interval.numerator}/{interval.denominator}")
    intervals.sort()
    return {
        "section_bars": [section["bars"] for section in project["form"]],
        "role_time_grid": role_grid,
        "root_anchor_deltas": anchor_deltas,
        "chord_steps": chord_steps,
        "lineage_edges": lineage_edges,
        "sounding_intervals": intervals,
    }


def fingerprint_record_from_project(
    project: dict[str, Any], lineage_index: dict[str, Any], spec: dict[str, Any]
) -> dict[str, Any]:
    project_hash = sha256_digest(project["compiler"]["build_id"].encode() + b"\0project/1.2.0\0" + canonical_bytes(project)[:-1])
    if lineage_index.get("project_hash") != project_hash:
        raise SearchArtifactError("LINEAGE_PROJECT_MISMATCH")
    return fingerprint_record(
        spec,
        fingerprint_payloads_from_project(project, lineage_index, spec),
        project_hash,
        manifest_digest("cps.lineage-index/v1", lineage_index),
    )


def _items(value: Any) -> list[bytes]:
    if not isinstance(value, list):
        raise SearchArtifactError("FINGERPRINT_PAYLOAD_INVALID")
    return [canonical_bytes(item) for item in value]


def _component_difference(left: Any, right: Any, algorithm: str) -> Fraction:
    left_items, right_items = _items(left), _items(right)
    if algorithm == "padded_hamming":
        size = max(len(left_items), len(right_items))
        if size == 0:
            return Fraction(0)
        matches = sum(
            index < len(left_items)
            and index < len(right_items)
            and left_items[index] == right_items[index]
            for index in range(size)
        )
        return Fraction(size - matches, size)
    if algorithm == "set_jaccard":
        left_set, right_set = set(left_items), set(right_items)
        union_set = left_set | right_set
        return Fraction(0) if not union_set else Fraction(len(union_set - (left_set & right_set)), len(union_set))
    if algorithm == "multiset_jaccard":
        left_counts, right_counts = Counter(left_items), Counter(right_items)
        keys = left_counts.keys() | right_counts.keys()
        union_count = sum(max(left_counts[key], right_counts[key]) for key in keys)
        intersection = sum(min(left_counts[key], right_counts[key]) for key in keys)
        return Fraction(0) if union_count == 0 else Fraction(union_count - intersection, union_count)
    raise SearchArtifactError("FINGERPRINT_DISTANCE_ALGORITHM_INVALID")


def fingerprint_distance_q(
    spec: dict[str, Any], left_payloads: dict[str, Any], right_payloads: dict[str, Any]
) -> int:
    expected = {item["id"] for item in spec["components"]}
    if set(left_payloads) != expected or set(right_payloads) != expected:
        raise SearchArtifactError("FINGERPRINT_COMPONENT_SET_INVALID")
    weighted = Fraction(0)
    weight_sum = 0
    for component in spec["components"]:
        weight = component["weight"]
        weight_sum += weight
        weighted += weight * _component_difference(
            left_payloads[component["id"]], right_payloads[component["id"]], component["distance"]
        )
    if weight_sum <= 0:
        raise SearchArtifactError("FINGERPRINT_WEIGHT_INVALID")
    return _round_half_even(Fraction(10_000, weight_sum) * weighted)


def stream_key(root_seed: int, cohort_index: int, path: Sequence[str]) -> bytes:
    if not 0 <= root_seed <= (1 << 64) - 1 or not 0 <= cohort_index <= (1 << 64) - 1:
        raise SearchArtifactError("SAMPLER_STREAM_RANGE")
    encoded = bytearray(b"cps.broad-prior/stream/v1\0" + struct.pack(">QQ", root_seed, cohort_index))
    for segment in path:
        normalized = unicodedata.normalize("NFC", segment)
        if normalized != segment:
            raise SearchArtifactError("CANONICAL_STRING_NOT_NFC")
        raw = normalized.encode("utf-8")
        encoded.extend(struct.pack(">I", len(raw)))
        encoded.extend(raw)
    return hashlib.sha256(encoded).digest()


def stream_draw(key: bytes, counter: int) -> int:
    if len(key) != 32 or not 0 <= counter <= (1 << 64) - 1:
        raise SearchArtifactError("SAMPLER_STREAM_RANGE")
    return struct.unpack(">Q", hashlib.sha256(key + struct.pack(">Q", counter)).digest()[:8])[0]


def choose_weighted(table: Sequence[dict[str, Any]], draw: int) -> tuple[int, Any]:
    if not 0 <= draw <= (1 << 64) - 1:
        raise SearchArtifactError("SAMPLER_DRAW_RANGE")
    total = 0
    for entry in table:
        weight = entry.get("weight")
        if type(weight) is not int or not 0 <= weight <= (1 << 64) - 1:
            raise SearchArtifactError("SAMPLER_WEIGHT_INVALID")
        total += weight
        if total > (1 << 64) - 1:
            raise SearchArtifactError("SAMPLER_WEIGHT_SUM_INVALID")
    if total == 0:
        raise SearchArtifactError("SAMPLER_WEIGHT_SUM_INVALID")
    point, cumulative = draw % total, 0
    for index, entry in enumerate(table):
        cumulative += entry["weight"]
        if point < cumulative:
            return index, entry["value"]
    raise AssertionError("positive cumulative table did not select")


def sampler_choice(root_seed: int, cohort_index: int, path: Sequence[str], counter: int, table: Sequence[dict[str, Any]]) -> tuple[int, Any]:
    return choose_weighted(table, stream_draw(stream_key(root_seed, cohort_index, path), counter))


def action_id(run_hash: str, round_index: int, phase_ordinal: int, candidate_ordinal: int) -> str:
    try:
        raw_hash = bytes.fromhex(run_hash.removeprefix("sha256:"))
    except ValueError as error:
        raise SearchArtifactError("RUN_HASH_INVALID") from error
    if not run_hash.startswith("sha256:") or len(raw_hash) != 32:
        raise SearchArtifactError("RUN_HASH_INVALID")
    if not 0 <= round_index <= (1 << 64) - 1 or not 0 <= candidate_ordinal <= (1 << 64) - 1 or not 0 <= phase_ordinal <= 7:
        raise SearchArtifactError("ACTION_RANGE_INVALID")
    preimage = b"cps.search-action/v1\0" + raw_hash + struct.pack(">QIQ", round_index, phase_ordinal, candidate_ordinal)
    return "act_" + base64.b32encode(hashlib.sha256(preimage).digest()).decode("ascii").lower().rstrip("=")[:26]


def seal_record(record: dict[str, Any]) -> dict[str, Any]:
    core = dict(record)
    core.pop("record_hash", None)
    sealed = dict(core)
    sealed["record_hash"] = manifest_digest("cps.search-run-record/v1", core)
    return sealed


@dataclass(frozen=True)
class ArchiveCandidate:
    program_hash: str
    project_hash: str
    lineage_root_hash: str
    quality: tuple[int, int, int, int, int]

    def wire(self) -> dict[str, Any]:
        return {"program_hash": self.program_hash, "project_hash": self.project_hash, "lineage_root_hash": self.lineage_root_hash, "quality": list(self.quality)}


def archive_cell(value: int | None, edges: Sequence[int]) -> int | None:
    if value is None:
        return None
    for index in range(len(edges) - 1):
        if edges[index] <= value < edges[index + 1]:
            return index
    raise SearchArtifactError("DESCRIPTOR_BIN_INVALID")


def update_archive_record(qd_manifest_hash: str, cell: Sequence[int], revision: int, candidates: Sequence[ArchiveCandidate], previous_record_hash: str | None) -> dict[str, Any]:
    """Select a champion and lineage-root-diverse runners in frozen total order."""
    if not candidates:
        raise SearchArtifactError("QD_CANDIDATE_EMPTY")
    ordered = sorted(candidates, key=lambda item: (tuple(-value for value in item.quality), item.program_hash.encode("utf-8")))
    champion = ordered[0]
    retained: list[ArchiveCandidate] = []
    roots = {champion.lineage_root_hash}
    for candidate in ordered[1:]:
        if candidate.lineage_root_hash not in roots:
            retained.append(candidate)
            roots.add(candidate.lineage_root_hash)
            if len(retained) == 4:
                break
    return {"schema": "cps.qd-archive-record", "schema_version": "1.0.0", "qd_manifest_hash": qd_manifest_hash, "cell": list(cell), "revision": revision, "champion": champion.wire(), "runners": [item.wire() for item in retained], "previous_record_hash": previous_record_hash}


class LocalRunStore:
    """CAS plus length-framed append-only records for one local search run."""

    def __init__(self, root: Path, run_hash: str) -> None:
        self.root = root
        self.run_hash = run_hash
        self.cas_root = root / "cas" / "sha256"
        self.records_path = root / "runs" / run_hash.removeprefix("sha256:") / "records.log"

    def put(self, payload: bytes) -> str:
        digest = sha256_digest(payload)
        hex_digest = digest.removeprefix("sha256:")
        target = self.cas_root / hex_digest[:2] / hex_digest[2:]
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_bytes() != payload:
                raise SearchArtifactError("CAS_HASH_COLLISION")
            return digest
        descriptor, temporary = tempfile.mkstemp(prefix=".cps-", dir=target.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                if target.read_bytes() != payload:
                    raise SearchArtifactError("CAS_HASH_COLLISION")
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            directory = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except BaseException:
            if os.path.exists(temporary):
                os.unlink(temporary)
            raise
        return digest

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        sealed = seal_record(record)
        payload_hash = sealed.get("payload_hash")
        if not isinstance(payload_hash, str) or not self._cas_path(payload_hash).is_file():
            raise SearchArtifactError("RUN_RECORD_PAYLOAD_MISSING")
        self.records_path.parent.mkdir(parents=True, exist_ok=True)
        encoded = canonical_bytes(sealed)
        with self.records_path.open("ab") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                handle.write(struct.pack(">Q", len(encoded)))
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return sealed

    def _cas_path(self, digest: str) -> Path:
        hex_digest = digest.removeprefix("sha256:")
        return self.cas_root / hex_digest[:2] / hex_digest[2:]

    def records(self) -> list[dict[str, Any]]:
        """Read and verify the local append-only record framing and hash chain."""
        if not self.records_path.exists():
            return []
        payload = self.records_path.read_bytes()
        cursor, previous, records = 0, None, []
        while cursor < len(payload):
            if len(payload) - cursor < 8:
                raise SearchArtifactError("RUN_RECORD_TRUNCATED")
            size = struct.unpack(">Q", payload[cursor : cursor + 8])[0]
            cursor += 8
            if len(payload) - cursor < size:
                raise SearchArtifactError("RUN_RECORD_TRUNCATED")
            encoded = payload[cursor : cursor + size]
            cursor += size
            try:
                record = json.loads(encoded)
            except ValueError as error:
                raise SearchArtifactError("RUN_RECORD_INVALID") from error
            if canonical_bytes(record) != encoded or record != seal_record(record):
                raise SearchArtifactError("RUN_RECORD_INVALID")
            if record.get("run_hash") != self.run_hash or record.get("sequence") != len(records) or record.get("previous_record_hash") != previous:
                raise SearchArtifactError("RUN_RECORD_CHAIN_INVALID")
            if not self._cas_path(record["payload_hash"]).is_file():
                raise SearchArtifactError("RUN_RECORD_PAYLOAD_MISSING")
            previous = record["record_hash"]
            records.append(record)
        return records


class SearchLoopError(ValueError):
    """Closed production-search loop error; no planner or evaluator fallback."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class SearchLoopSeams:
    """Explicit external boundaries for proposal, rendering, and evaluation.

    ``propose`` returns one fully formed MutationApplicationRequest.  This is
    intentional: it preserves the typed mutation request's catalog, lock and
    base-program bindings instead of recreating them in the search loop.
    """

    propose: Callable[[str, int, int, dict[str, Any]], dict[str, Any]]
    evaluate: Callable[[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]]
    render: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    compiler: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None


@dataclass(frozen=True)
class SearchLoopResult:
    run_hash: str
    completed_candidates: int
    compile_logical_units: int
    render_frames: int
    archive_heads: dict[tuple[int, int], str]
    last_checkpoint_hash: str | None


class ProductionSearchLoop:
    """Append-only, deterministic production orchestration around connected work.

    Candidate execution is delegated to :func:`execute_connected`; this class
    owns only action ordering, durable records/checkpoints, descriptor and
    fingerprint extraction, and QD archive publication.  It deliberately does
    not synthesize planner, renderer, or evaluator outputs.
    """

    def __init__(
        self,
        root: Path,
        run_manifest: dict[str, Any],
        *,
        executor_manifest: dict[str, Any],
        compiler_manifest: dict[str, Any],
        descriptor_spec: dict[str, Any],
        fingerprint_spec: dict[str, Any],
        qd_manifest: dict[str, Any],
        seams: SearchLoopSeams,
    ) -> None:
        from .connected import executor_manifest_digest

        self.run_manifest, self.executor_manifest = deepcopy(run_manifest), deepcopy(executor_manifest)
        self.compiler_manifest, self.descriptor_spec = deepcopy(compiler_manifest), deepcopy(descriptor_spec)
        self.fingerprint_spec, self.qd_manifest, self.seams = deepcopy(fingerprint_spec), deepcopy(qd_manifest), seams
        self.run_hash = manifest_digest("cps.search-run-manifest/v1", self.run_manifest)
        self.store = LocalRunStore(root, self.run_hash)
        self._validate_manifests(executor_manifest_digest)
        self.executor_manifest_digest = executor_manifest_digest(self.executor_manifest)
        self.history = self.store.records()
        self.sequence = len(self.history)
        self.previous_hash = self.history[-1]["record_hash"] if self.history else None
        self.completed = sum(item["kind"] == "candidate" for item in self.history)
        self.compile_used = 0
        self.render_used = 0
        self.archive_heads: dict[tuple[int, int], str] = {}
        self.archive_candidates: dict[tuple[int, int], list[ArchiveCandidate]] = {}
        self.archive_revisions: dict[tuple[int, int], int] = {}
        self.last_checkpoint_hash: str | None = None
        self._resumed_program: dict[str, Any] | None = None
        self.initial_lineage_seeds: dict[str, dict[str, str]] | None = None
        self._resume_checkpoint()

    def _validate_manifests(self, executor_digest: Callable[[dict[str, Any]], str]) -> None:
        run = self.run_manifest
        if run.get("schema") != "cps.search-run-manifest" or run.get("schema_version") != "1.2.0":
            raise SearchLoopError("RUN_MANIFEST_INVALID")
        expected = {
            "compiler_manifest_hash": manifest_digest("cps.compiler-manifest/v1.1", self.compiler_manifest),
            "qd_manifest_hash": manifest_digest("cps.qd-manifest/v1", self.qd_manifest),
        }
        for key, digest in expected.items():
            if run.get(key) != digest: raise SearchLoopError("RUN_MANIFEST_BINDING_MISMATCH")
        if self.qd_manifest.get("descriptor_spec_hash") != manifest_digest("cps.descriptor-spec/v1", self.descriptor_spec):
            raise SearchLoopError("QD_MANIFEST_BINDING_MISMATCH")
        if self.qd_manifest.get("fingerprint_spec_hash") != manifest_digest("cps.fingerprint-spec/v1", self.fingerprint_spec):
            raise SearchLoopError("QD_MANIFEST_BINDING_MISMATCH")
        if executor_digest(self.executor_manifest)[:7] != "sha256:": raise SearchLoopError("EXECUTOR_MANIFEST_INVALID")

    def _resume_checkpoint(self) -> None:
        """Use the latest checkpoint only after its referenced record is known."""
        for record in reversed(self.history):
            if record["kind"] != "checkpoint": continue
            try:
                checkpoint = json.loads(self.store._cas_path(record["payload_hash"]).read_bytes())
                if checkpoint["run_hash"] != self.run_hash: continue
                if checkpoint["last_sequence"] >= record["sequence"]: continue
                if checkpoint["last_record_hash"] != self.history[checkpoint["last_sequence"]]["record_hash"]: continue
                self.compile_used = checkpoint["budget_usage"]["compile_logical_units"]
                self.render_used = checkpoint["budget_usage"]["render_frames"]
                self.archive_heads = {tuple(item["cell"]): item["record_hash"] for item in checkpoint["archive_heads"]}
                for archive_record in self.history[: record["sequence"]]:
                    if archive_record["kind"] != "archive_update": continue
                    archive = json.loads(self.store._cas_path(archive_record["payload_hash"]).read_bytes())
                    cell = tuple(archive["cell"])
                    self.archive_revisions[cell] = archive["revision"]
                    self.archive_candidates[cell] = [
                        ArchiveCandidate(item["program_hash"], item["project_hash"], item["lineage_root_hash"], tuple(item["quality"]))
                        for item in [archive["champion"], *archive["runners"]]
                    ]
                self.last_checkpoint_hash = record["record_hash"]
                for candidate_record in reversed(self.history[: record["sequence"]]):
                    if candidate_record["kind"] != "candidate": continue
                    output = json.loads(self.store._cas_path(candidate_record["payload_hash"]).read_bytes())
                    if output.get("status") == "success" and isinstance(output.get("resulting_program"), dict):
                        self._resumed_program = output["resulting_program"]
                        break
                return
            except (KeyError, IndexError, ValueError, OSError):
                continue

    def _record(self, kind: str, round_index: int, phase: int, candidate: int, payload: dict[str, Any]) -> dict[str, Any]:
        payload_hash = self.store.put(canonical_bytes(payload))
        record = self.store.append({"schema": "cps.search-run-record", "schema_version": "1.0.0", "run_hash": self.run_hash,
                                    "sequence": self.sequence, "action_id": action_id(self.run_hash, round_index, phase, candidate),
                                    "round": round_index, "phase_ordinal": phase, "candidate_ordinal": candidate,
                                    "kind": kind, "payload_hash": payload_hash, "previous_record_hash": self.previous_hash})
        self.sequence += 1; self.previous_hash = record["record_hash"]
        return record

    def _checkpoint(self, round_index: int, candidate: int) -> None:
        if self.previous_hash is None: return
        next_round, next_candidate = divmod(
            round_index * self.run_manifest["candidates_per_round"] + candidate + 1,
            self.run_manifest["candidates_per_round"],
        )
        heads = [{"cell": list(cell), "record_hash": digest} for cell, digest in sorted(self.archive_heads.items())]
        checkpoint = {"schema": "cps.search-checkpoint", "schema_version": "1.0.0", "run_hash": self.run_hash,
                      "last_sequence": self.sequence - 1, "last_record_hash": self.previous_hash,
                      "next_action_id": action_id(self.run_hash, next_round, 0, next_candidate),
                      "cursor": {"round": next_round, "candidate_ordinal": next_candidate, "phase_ordinal": 0},
                      "budget_usage": {"compile_logical_units": self.compile_used, "render_frames": self.render_used, "planner_calls": self.completed},
                      "planner_calls": self.completed, "patience_rounds": 0, "cancelled": False,
                      "archive_heads": heads, "champions": []}
        record = self._record("checkpoint", round_index, 7, candidate, checkpoint)
        self.last_checkpoint_hash = record["record_hash"]

    def _cell(self, descriptor: dict[str, Any]) -> tuple[int, int] | None:
        axes = self.descriptor_spec["axes"]
        values = (descriptor["rhythmic_syncopation_q"], descriptor["material_recurrence_distance_q"])
        bins = tuple(archive_cell(value, axis["bin_edges"]) for value, axis in zip(values, axes, strict=True))
        return None if any(value is None for value in bins) else bins  # null is explicitly not archived in v1

    def _archive(self, candidate: ArchiveCandidate, cell: tuple[int, int], round_index: int, candidate_ordinal: int) -> None:
        candidates = self.archive_candidates.setdefault(cell, [])
        candidates.append(candidate)
        revision = self.archive_revisions.get(cell, -1) + 1
        record = update_archive_record(manifest_digest("cps.qd-manifest/v1", self.qd_manifest), cell, revision, candidates, self.archive_heads.get(cell))
        archive_record = self._record("archive_update", round_index, 6, candidate_ordinal, record)
        self.archive_heads[cell] = archive_record["record_hash"]
        self.archive_revisions[cell] = revision

    def run(self, base_program: dict[str, Any], *, maximum_candidates: int | None = None) -> SearchLoopResult:
        """Run bounded candidates, committing every semantic event before advance."""
        from .compiler import build_lineage_index, initial_material_lineage_seeds
        from .connected import ConnectedCache, execute_connected

        limit = self.run_manifest["maximum_rounds"] * self.run_manifest["candidates_per_round"]
        if maximum_candidates is not None: limit = min(limit, maximum_candidates)
        cache = ConnectedCache(self.store.root)
        current = deepcopy(self._resumed_program if self._resumed_program is not None else base_program)
        if self.initial_lineage_seeds is None:
            self.initial_lineage_seeds = initial_material_lineage_seeds(base_program)
        for ordinal in range(self.completed, limit):
            round_index, candidate_ordinal = divmod(ordinal, self.run_manifest["candidates_per_round"])
            if self.completed >= self.run_manifest["planner_call_budget"]:
                self._record("failure", round_index, 1, candidate_ordinal, {"code": "PLANNER_CALL_BUDGET_EXCEEDED", "used": self.completed})
                self._checkpoint(round_index, candidate_ordinal)
                break
            from .mutation import program_hash
            sample = {"base_program_hash": program_hash(current), "root_seed": self.run_manifest["root_seed"], "cohort_index": ordinal}
            self._record("run" if ordinal == 0 and self.sequence == 0 else "planner_request", round_index, 0, candidate_ordinal, sample)
            proposal = self.seams.propose(action_id(self.run_hash, round_index, 1, candidate_ordinal), round_index, candidate_ordinal, deepcopy(current))
            if not isinstance(proposal, dict) or proposal.get("base_program") != current:
                raise SearchLoopError("PROPOSAL_BASE_PROGRAM_MISMATCH")
            self._record("planner_response", round_index, 1, candidate_ordinal, proposal)
            connected = {"schema": "cps.connected-request", "schema_version": "1.0.0", "executor_manifest_digest": self.executor_manifest_digest, "executor_manifest": self.executor_manifest, "mutation_request": proposal, "compiler_manifest": self.compiler_manifest}
            execution = execute_connected(connected, self.seams.compiler, cache)
            output = execution.output
            self._record("candidate", round_index, 3, candidate_ordinal, output)
            report = output["compile_report"]
            charge = 0 if report is None else report["receipt"]["usage"]["total_logical_units"]
            if self.compile_used + charge > self.run_manifest["compile_logical_budget"]:
                self._record("failure", round_index, 3, candidate_ordinal, {"code": "RUN_COMPILE_BUDGET_EXCEEDED", "charge": charge, "used": self.compile_used})
                self._checkpoint(round_index, candidate_ordinal)
                break
            self.compile_used += charge
            if output["status"] != "success":
                self._record("failure", round_index, 2, candidate_ordinal, {"status": output["status"], "error": output["error"]})
                self.completed += 1; self._checkpoint(round_index, candidate_ordinal); continue
            project = output["project"]
            try:
                lineage = build_lineage_index(output["resulting_program"], project, self.initial_lineage_seeds)
                descriptor = descriptor_result_from_project(project, lineage, self.descriptor_spec)
                fingerprint = fingerprint_record_from_project(project, lineage, self.fingerprint_spec)
            except SearchArtifactError as error:
                self._record("failure", round_index, 5, candidate_ordinal, {"code": error.code, "stage": "evaluate"})
                self.completed += 1; self._checkpoint(round_index, candidate_ordinal); continue
            self._record("metric_report", round_index, 5, candidate_ordinal, {"descriptor": descriptor, "fingerprint": fingerprint, "lineage_index": lineage})
            if self.seams.render is not None:
                render = self.seams.render(project)
                frames = render.get("frames", render.get("frame_count", 0))
                if not isinstance(frames, int) or frames < 0 or self.render_used + frames > self.run_manifest["render_frame_budget"]:
                    raise SearchLoopError("RENDER_BUDGET_EXCEEDED")
                self.render_used += frames
                self._record("artifact_reference", round_index, 4, candidate_ordinal, render)
            evaluation = self.seams.evaluate(project, descriptor, fingerprint, output)
            quality = tuple(evaluation.get("quality", ()))
            if len(quality) != 5 or any(type(value) is not int for value in quality): raise SearchLoopError("EVALUATION_QUALITY_INVALID")
            evaluation_record = self._record("acceptance_decision", round_index, 5, candidate_ordinal, evaluation)
            cell = self._cell(descriptor)
            if cell is not None:
                candidate = ArchiveCandidate(output["mutation_receipt"]["result_program_hash"], report["project_hash"], lineage["program_lineage_root_hash"], quality)
                self._archive(candidate, cell, round_index, candidate_ordinal)
            current = deepcopy(output["resulting_program"])
            self.completed += 1
            self._checkpoint(round_index, candidate_ordinal)
        return SearchLoopResult(self.run_hash, self.completed, self.compile_used, self.render_used, dict(self.archive_heads), self.last_checkpoint_hash)
