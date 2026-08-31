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
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence


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
