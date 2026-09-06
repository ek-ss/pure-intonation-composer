"""Connected candidate execution, whole-result cache, and ordered runner.

The compiler owns GEN0-B receipts/opcodes.  This module deliberately owns only
the outer protocol: mutation is applied before compilation, cache entries are
validated as one indivisible value, and runner publication is ordinal ordered.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unicodedata
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from .mutation import apply_mutation_request


class ConnectedExecutionError(ValueError):
    """A closed connected-execution/protocol failure."""

    def __init__(self, code: str, stage: str = "connected") -> None:
        super().__init__(code)
        self.code, self.stage = code, stage


class CompilerReceiptExecutor(Protocol):
    """Seam supplied by the GEN0-B receipt implementation.

    It returns ``status`` (``success`` or ``compile_failure``), ``project``,
    ``compiler_evidence``, ``melody_report``, ``compile_report``,
    ``opcode_stream_bundle``, and ``error``.  A compile failure has null
    project/evidence/melody/bundle and a non-null CompileReport/error.
    """

    def __call__(self, program: dict[str, Any], compiler_manifest: dict[str, Any]) -> dict[str, Any]: ...


def _quote(value: str) -> str:
    if unicodedata.normalize("NFC", value) != value:
        raise ConnectedExecutionError("CANONICAL_JSON_INVALID", "canonical")
    chunks = ['"']
    escapes = {8: "\\b", 9: "\\t", 10: "\\n", 12: "\\f", 13: "\\r"}
    for char in value:
        point = ord(char)
        if char == '"': chunks.append('\\"')
        elif char == "\\": chunks.append("\\\\")
        elif point in escapes: chunks.append(escapes[point])
        elif point < 0x20: chunks.append(f"\\u{point:04x}")
        elif 0xD800 <= point <= 0xDFFF: raise ConnectedExecutionError("CANONICAL_JSON_INVALID", "canonical")
        else: chunks.append(char)
    return "".join(chunks) + '"'


def _encode(value: Any) -> str:
    if value is None: return "null"
    if value is True: return "true"
    if value is False: return "false"
    if isinstance(value, int): return str(value)
    if isinstance(value, float): raise ConnectedExecutionError("CANONICAL_JSON_INVALID", "canonical")
    if isinstance(value, str): return _quote(value)
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value): raise ConnectedExecutionError("CANONICAL_JSON_INVALID", "canonical")
        return "{" + ",".join(f"{_quote(key)}:{_encode(value[key])}" for key in sorted(value, key=lambda item: item.encode())) + "}"
    if isinstance(value, (list, tuple)): return "[" + ",".join(_encode(item) for item in value) + "]"
    raise ConnectedExecutionError("CANONICAL_JSON_INVALID", "canonical")


def canonical_bytes(value: Any) -> bytes:
    return _encode(value).encode("utf-8")


def canonical_lf(value: Any) -> bytes:
    return canonical_bytes(value) + b"\n"


def artifact_hash(domain: str, value: Any, *, omit: str | None = None) -> str:
    core = deepcopy(value)
    if omit is not None:
        if not isinstance(core, dict): raise ConnectedExecutionError("HASH_INPUT_INVALID", "hash")
        core.pop(omit, None)
    return "sha256:" + hashlib.sha256(domain.encode() + b"\0" + canonical_lf(core)).hexdigest()


def connected_request_hash(request: dict[str, Any]) -> str: return artifact_hash("cps.connected-request/v1", request)
def executor_manifest_digest(manifest: dict[str, Any]) -> str: return artifact_hash("cps.connected-executor-manifest/v1", manifest)
def logical_output_hash(output: dict[str, Any]) -> str: return artifact_hash("cps.connected-logical-output/v1", output, omit="logical_output_hash")
def cache_entry_hash(entry: dict[str, Any]) -> str: return artifact_hash("cps.connected-cache-entry/v1", entry, omit="entry_hash")
def opcode_bundle_hash(bundle: dict[str, Any]) -> str: return artifact_hash("cps.opcode-stream-bundle/v1", bundle, omit="bundle_hash")


def cache_key(request: dict[str, Any]) -> dict[str, str]:
    core = {"request_hash": connected_request_hash(request), "executor_manifest_digest": executor_manifest_digest(request["executor_manifest"])}
    return {**core, "cache_key_hash": artifact_hash("cps.connected-cache-key/v1", core)}


def _receipt_hash(receipt: dict[str, Any]) -> str:
    return artifact_hash("cps.mutation-application-receipt/v1", receipt, omit="receipt_hash")


def _compile_receipt_hash(receipt: dict[str, Any]) -> str:
    return artifact_hash("cps.charge-receipt/v1.1", receipt)


def _stream_hash(stream: dict[str, Any]) -> str:
    return artifact_hash("cps.logical-opcode-stream/v1", stream, omit="stream_hash")


def _validate_stream(stream: dict[str, Any]) -> None:
    if stream.get("schema") != "cps.logical-opcode-stream" or stream.get("schema_version") != "1.0.0":
        raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "opcode_hash")
    if stream.get("stream_hash") != _stream_hash(stream): raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "opcode_hash")
    for ordinal, record in enumerate(stream.get("records", [])):
        if record.get("ordinal") != ordinal or not isinstance(record.get("charge"), int) or record["charge"] < 1:
            raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "opcode_hash")


def _validate_bundle(bundle: dict[str, Any], receipt: dict[str, Any]) -> None:
    if bundle.get("bundle_hash") != opcode_bundle_hash(bundle): raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "opcode_hash")
    _validate_stream(bundle["root"])
    if bundle["root"]["stream_hash"] != receipt.get("opcode_stream_hash"): raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "opcode_hash")
    children = receipt.get("children", [])
    if len(bundle.get("children", [])) != len(children): raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "opcode_hash")
    for stored, child in zip(bundle["children"], children, strict=True):
        stream = stored.get("stream", {})
        if (stored.get("kind"), stored.get("query_id")) != (child.get("kind"), child.get("query_id")):
            raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "opcode_hash")
        _validate_stream(stream)
        if (stream.get("input_hash"), stream.get("stream_hash")) != (child.get("input_hash"), child.get("opcode_stream_hash")):
            raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "opcode_hash")


def _validate_logical_output(output: dict[str, Any], request: dict[str, Any]) -> None:
    """Check the outer artifact invariants before a cache hit is visible."""
    if output.get("request_hash") != connected_request_hash(request):
        raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "cross_binding")
    status = output.get("status")
    if status == "mutation_failure":
        if any(output.get(key) is not None for key in ("resulting_program", "mutation_impact", "project", "compiler_evidence", "melody_report", "compile_report", "lineage_index")):
            raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "cross_binding")
    elif status == "compile_failure":
        if any(output.get(key) is not None for key in ("project", "compiler_evidence", "melody_report", "lineage_index")) or output.get("resulting_program") is None or output.get("mutation_impact") is None or output.get("compile_report") is None:
            raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "cross_binding")
    elif status == "success":
        if any(output.get(key) is None for key in ("resulting_program", "mutation_impact", "project", "compiler_evidence", "melody_report", "compile_report")) or output.get("lineage_index") is not None or output.get("error") is not None:
            raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "cross_binding")
    else:
        raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "schema")
    if status != "success": return
    project, evidence, melody, report = (output[key] for key in ("project", "compiler_evidence", "melody_report", "compile_report"))
    try:
        project_hash = "sha256:" + hashlib.sha256(project["compiler"]["build_id"].encode() + b"\0project/1.2.0\0" + canonical_bytes(project)).hexdigest()
        evidence_hash = artifact_hash("cps.gen0b-compiler-evidence/v1", evidence, omit="evidence_hash")
        melody_hash = artifact_hash("cps.chord-member-melody-report/v1", melody, omit="report_hash")
        if project_hash != report["project_hash"] or project_hash != evidence["project_hash"] or project_hash != melody["project_hash"]:
            raise KeyError
        if evidence_hash != evidence["evidence_hash"] or evidence_hash != report["evidence_hash"] or melody_hash != melody["report_hash"]:
            raise KeyError
        if report["receipt"]["input_hash"] is None or report["status"] != "success": raise KeyError
    except (KeyError, TypeError, ConnectedExecutionError):
        raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "artifact_hash") from None


def build_cache_entry(request: dict[str, Any], output: dict[str, Any], bundle: dict[str, Any] | None) -> dict[str, Any]:
    key = cache_key(request)
    if output.get("request_hash") != key["request_hash"] or output.get("logical_output_hash") != logical_output_hash(output):
        raise ConnectedExecutionError("CONNECTED_OUTPUT_INVALID")
    receipt = output["mutation_receipt"]
    if receipt.get("receipt_hash") != _receipt_hash(receipt): raise ConnectedExecutionError("CONNECTED_OUTPUT_INVALID")
    report = output.get("compile_report")
    if (report is None) != (bundle is None): raise ConnectedExecutionError("CONNECTED_OUTPUT_INVALID")
    if bundle is not None: _validate_bundle(bundle, report["receipt"])
    entry = {"schema": "cps.connected-cache-entry", "schema_version": "1.0.0", "key": key,
             "logical_output": deepcopy(output), "logical_output_hash": output["logical_output_hash"],
             "mutation_receipt_hash": receipt["receipt_hash"],
             "compile_receipt_hash": None if report is None else _compile_receipt_hash(report["receipt"]),
             "opcode_stream_bundle": deepcopy(bundle),
             "opcode_stream_bundle_hash": None if bundle is None else bundle["bundle_hash"]}
    entry["entry_hash"] = cache_entry_hash(entry)
    return entry


def validate_cache_entry(entry: dict[str, Any], request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if entry.get("key") != cache_key(request): raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "requested_key")
    if entry.get("entry_hash") != cache_entry_hash(entry): raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "entry_hash")
    output = entry.get("logical_output")
    if not isinstance(output, dict) or entry.get("logical_output_hash") != logical_output_hash(output) or output.get("logical_output_hash") != entry.get("logical_output_hash"):
        raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "logical_output_hash")
    _validate_logical_output(output, request)
    receipt = output.get("mutation_receipt")
    if not isinstance(receipt, dict) or receipt.get("receipt_hash") != _receipt_hash(receipt) or entry.get("mutation_receipt_hash") != receipt["receipt_hash"]:
        raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "receipt_hash")
    report, bundle = output.get("compile_report"), entry.get("opcode_stream_bundle")
    if (report is None) != (bundle is None): raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "cross_binding")
    if report is None:
        if entry.get("compile_receipt_hash") is not None or entry.get("opcode_stream_bundle_hash") is not None: raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "cross_binding")
    else:
        if entry.get("compile_receipt_hash") != _compile_receipt_hash(report["receipt"]): raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "receipt_hash")
        _validate_bundle(bundle, report["receipt"])
        if entry.get("opcode_stream_bundle_hash") != bundle["bundle_hash"]: raise ConnectedExecutionError("CACHE_RECEIPT_INVALID", "opcode_hash")
    return deepcopy(output), deepcopy(bundle)


class ConnectedCache:
    """Whole-entry cache; optional root uses the contract's CAS path."""
    def __init__(self, root: Path | None = None) -> None:
        self.root, self._entries = root, {}

    def _path(self, digest: str) -> Path:
        assert self.root is not None
        hex_digest = digest.removeprefix("sha256:")
        return self.root / "cas" / "connected-cache" / "sha256" / hex_digest[:2] / hex_digest[2:]

    def load(self, request: dict[str, Any]) -> dict[str, Any] | None:
        key = cache_key(request)["cache_key_hash"]
        if self.root is None: return deepcopy(self._entries.get(key))
        path = self._path(key)
        try: return json.loads(path.read_text("utf-8"))
        except (OSError, ValueError): return None

    def preseed_raw(self, request: dict[str, Any], payload: dict[str, Any]) -> None:
        """Install an isolated test/transport namespace entry verbatim.

        Validation intentionally happens on lookup so this can model the exact
        corrupt namespace defined by the runner contract.
        """
        key = cache_key(request)["cache_key_hash"]
        if self.root is not None:
            path = self._path(key); path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(canonical_lf(payload))
        else: self._entries[key] = deepcopy(payload)

    def discard(self, request: dict[str, Any]) -> None:
        """Remove a privately-invalid entry before mandatory recomputation."""
        key = cache_key(request)["cache_key_hash"]
        if self.root is None:
            self._entries.pop(key, None)
        else:
            try: self._path(key).unlink()
            except FileNotFoundError: pass

    def publish(self, request: dict[str, Any], entry: dict[str, Any]) -> None:
        key = cache_key(request)["cache_key_hash"]
        if self.root is None:
            prior = self._entries.setdefault(key, deepcopy(entry))
            if canonical_lf(prior) != canonical_lf(entry): raise ConnectedExecutionError("DETERMINISM_VIOLATION", "cache_publish")
            return
        path = self._path(key); path.parent.mkdir(parents=True, exist_ok=True)
        payload = canonical_lf(entry)
        try:
            descriptor, temporary = tempfile.mkstemp(prefix=".connected-", dir=path.parent)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload); handle.flush(); os.fsync(handle.fileno())
            try: os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != payload: raise ConnectedExecutionError("DETERMINISM_VIOLATION", "cache_publish")
            finally:
                try: os.unlink(temporary)
                except FileNotFoundError: pass
        except OSError as exc: raise ConnectedExecutionError("CACHE_PUBLISH_FAILED", "cache_publish") from exc


@dataclass(frozen=True)
class ConnectedExecution:
    output: dict[str, Any]
    opcode_stream_bundle: dict[str, Any] | None
    telemetry: dict[str, int]


def _mutation_output(request: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    error = result["error"]
    output = {"schema": "cps.connected-logical-output", "schema_version": "1.0.0", "request_hash": connected_request_hash(request),
              "status": "mutation_failure", "resulting_program": None, "mutation_impact": None,
              "mutation_receipt": result["receipt"], "project": None, "compiler_evidence": None,
              "melody_report": None, "compile_report": None, "lineage_index": None,
              "error": {key: error[key] for key in ("code", "stage", "pointer")}, "logical_output_hash": ""}
    output["logical_output_hash"] = logical_output_hash(output)
    return output


def _complete_output(request: dict[str, Any], mutation: dict[str, Any], stage: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    status = stage.get("status")
    if status not in {"success", "compile_failure"}: raise ConnectedExecutionError("CONNECTED_COMPILER_RESULT_INVALID", "compiler")
    error = stage.get("error")
    output = {"schema": "cps.connected-logical-output", "schema_version": "1.0.0", "request_hash": connected_request_hash(request),
              "status": status, "resulting_program": mutation["program"], "mutation_impact": mutation["impact"],
              "mutation_receipt": mutation["receipt"], "project": stage.get("project"),
              "compiler_evidence": stage.get("compiler_evidence"), "melody_report": stage.get("melody_report"),
              "compile_report": stage.get("compile_report"), "lineage_index": None, "error": error,
              "logical_output_hash": ""}
    bundle = stage.get("opcode_stream_bundle")
    if status == "success":
        if any(output[key] is None for key in ("project", "compiler_evidence", "melody_report", "compile_report")) or error is not None: raise ConnectedExecutionError("CONNECTED_COMPILER_RESULT_INVALID", "compiler")
    else:
        if any(output[key] is not None for key in ("project", "compiler_evidence", "melody_report")) or output["compile_report"] is None or not isinstance(error, dict): raise ConnectedExecutionError("CONNECTED_COMPILER_RESULT_INVALID", "compiler")
    if (output["compile_report"] is None) != (bundle is None): raise ConnectedExecutionError("CONNECTED_COMPILER_RESULT_INVALID", "compiler")
    output["logical_output_hash"] = logical_output_hash(output)
    return output, bundle


def validate_connected_request(request: dict[str, Any]) -> None:
    if set(request) != {"schema", "schema_version", "executor_manifest_digest", "executor_manifest", "mutation_request", "compiler_manifest"} or request.get("schema") != "cps.connected-request" or request.get("schema_version") != "1.0.0":
        raise ConnectedExecutionError("CONNECTED_REQUEST_INVALID", "request")
    if request["executor_manifest_digest"] != executor_manifest_digest(request["executor_manifest"]): raise ConnectedExecutionError("EXECUTOR_MANIFEST_DIGEST_MISMATCH", "request")


def execute_connected(request: dict[str, Any], compiler: CompilerReceiptExecutor | None, cache: ConnectedCache | None = None) -> ConnectedExecution:
    """Execute one task with whole-entry cold/hit semantics.

    ``compiler`` must be the receipt-capable GEN0-B integration; the old
    ``compile_sp0`` project-only API is intentionally not accepted here.
    """
    validate_connected_request(request)
    if cache is not None:
        entry = cache.load(request)
        if entry is not None:
            try:
                output, bundle = validate_cache_entry(entry, request)
                return ConnectedExecution(output, bundle, {"lookups": 1, "hits": 1, "misses": 0, "corrupt_entries": 0, "recomputations": 0})
            except ConnectedExecutionError:
                corrupt = 1
                cache.discard(request)
        else: corrupt = 0
    else: corrupt = 0
    mutation = apply_mutation_request(request["mutation_request"])
    if mutation["status"] == "failure": output, bundle = _mutation_output(request, mutation), None
    else:
        if compiler is None:
            # Kept lazy so mutation-only deployments do not load the compiler.
            try:
                from .compiler import compile_connected_gen0b
            except ImportError as error:
                raise ConnectedExecutionError("CONNECTED_COMPILER_RECEIPT_API_UNAVAILABLE", "compiler") from error
            compiler = compile_connected_gen0b
        output, bundle = _complete_output(request, mutation, compiler(mutation["program"], request["compiler_manifest"]))
    if cache is not None: cache.publish(request, build_cache_entry(request, output, bundle))
    return ConnectedExecution(output, bundle, {"lookups": 1 if cache is not None else 0, "hits": 0, "misses": 1 if cache is not None and not corrupt else 0, "corrupt_entries": corrupt, "recomputations": 1})


def semantic_input_hash(case_pairs: list[dict[str, str]], ceiling: int) -> str:
    return artifact_hash("cps.connected-runner-input/v1", {"cases": case_pairs, "global_compile_logical_ceiling": ceiling})


def semantic_runner_request_hash(request: dict[str, Any]) -> str:
    return artifact_hash("cps.connected-runner-semantic-request/v1", {key: deepcopy(value) for key, value in request.items() if key != "execution"})


def run_connected_batch(request: dict[str, Any], cases: list[tuple[str, dict[str, Any]]], compiler: CompilerReceiptExecutor | None, cache: ConnectedCache | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run requested cases in logical ordinal order; workers only affect sidecar."""
    execution = request.get("execution", {})
    workers = execution.get("worker_count")
    if workers not in (1, 2, 4, 8): raise ConnectedExecutionError("RUN_WORKER_COUNT_INVALID", "runner")
    expected = [{"case_id": case_id, "connected_request_hash": connected_request_hash(value)} for case_id, value in cases]
    if request.get("case_ids") != [item["case_id"] for item in expected] or request.get("semantic_input_hash") != semantic_input_hash(expected, request.get("global_compile_logical_ceiling")):
        raise ConnectedExecutionError("RUN_REQUEST_BINDING_INVALID", "runner")
    used, published, telemetry = 0, [], []
    for ordinal, (case_id, connected) in enumerate(cases):
        result = execute_connected(connected, compiler, cache)
        telemetry.append({**result.telemetry, "schema": "cps.connected-execution-telemetry", "schema_version": "1.0.0", "cache_mode": execution.get("cache_mode"), "worker_count": workers, "physical_completed_ordinals": [ordinal]})
        charge = 0 if result.output["compile_report"] is None else result.output["compile_report"]["receipt"]["usage"]["total_logical_units"]
        ceiling = request["global_compile_logical_ceiling"]
        if used + charge > ceiling:
            failure = {"task_ordinal": ordinal, "case_id": case_id, "code": "RUN_COMPILE_BUDGET_EXCEEDED", "stage": "publish_budget", "counter": "total_logical_units", "requested": charge, "used": used, "ceiling": ceiling}
            break
        used += charge; failure = None
        published.append({"task_ordinal": ordinal, "case_id": case_id, "logical_output_hash": result.output["logical_output_hash"], "logical_output": result.output})
    result = {"schema": "cps.connected-runner-result", "schema_version": "1.0.0", "semantic_request_hash": semantic_runner_request_hash(request), "status": "failure" if failure else "success", "published_results": published, "failure": failure, "global_budget_used": used}
    result["result_hash"] = artifact_hash("cps.connected-runner-result/v1", result, omit="result_hash")
    return result, telemetry
