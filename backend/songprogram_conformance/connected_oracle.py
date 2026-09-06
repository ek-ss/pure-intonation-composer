"""Independent oracle for the connected-cache and runner envelopes.

This module deliberately treats the mutation/compiler products as opaque,
already-verified canonical artifacts.  It defines only the outer identities,
cache validation/fallback, and worker-independent runner projection.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any

from .canonical import canonical_bytes


class ConnectedOracleError(ValueError):
    pass


def canonical_lf(value: Any) -> bytes:
    return canonical_bytes(value) + b"\n"


def artifact_hash(domain: str, value: Any, *, omit: str | None = None) -> str:
    core = deepcopy(value)
    if omit is not None:
        if not isinstance(core, dict):
            raise ConnectedOracleError("hash omission requires an object")
        core.pop(omit, None)
    payload = domain.encode("utf-8") + b"\0" + canonical_lf(core)
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def raw_hash(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def connected_request_hash(request: dict[str, Any]) -> str:
    return artifact_hash("cps.connected-request/v1", request)


def executor_manifest_digest(manifest: dict[str, Any]) -> str:
    return artifact_hash("cps.connected-executor-manifest/v1", manifest)


def logical_output_hash(output: dict[str, Any]) -> str:
    return artifact_hash("cps.connected-logical-output/v1", output, omit="logical_output_hash")


def opcode_bundle_hash(bundle: dict[str, Any]) -> str:
    return artifact_hash("cps.opcode-stream-bundle/v1", bundle, omit="bundle_hash")


def cache_key(request_hash: str, manifest_digest: str) -> dict[str, str]:
    core = {"request_hash": request_hash, "executor_manifest_digest": manifest_digest}
    return {**core, "cache_key_hash": artifact_hash("cps.connected-cache-key/v1", core)}


def cache_entry_hash(entry: dict[str, Any]) -> str:
    return artifact_hash("cps.connected-cache-entry/v1", entry, omit="entry_hash")


def mutation_receipt_hash(receipt: dict[str, Any]) -> str:
    return artifact_hash(
        "cps.mutation-application-receipt/v1", receipt, omit="receipt_hash"
    )


def compile_receipt_hash(receipt: dict[str, Any]) -> str:
    return artifact_hash("cps.charge-receipt/v1.1", receipt)


def build_cache_entry(
    request: dict[str, Any], output: dict[str, Any], bundle: dict[str, Any] | None
) -> dict[str, Any]:
    request_digest = connected_request_hash(request)
    manifest_digest = executor_manifest_digest(request["executor_manifest"])
    if request["executor_manifest_digest"] != manifest_digest:
        raise ConnectedOracleError("executor manifest digest mismatch")
    if output["request_hash"] != request_digest:
        raise ConnectedOracleError("logical output request hash mismatch")
    output_digest = logical_output_hash(output)
    if output["logical_output_hash"] != output_digest:
        raise ConnectedOracleError("logical output hash mismatch")
    mutation_receipt_digest = mutation_receipt_hash(output["mutation_receipt"])
    if output["mutation_receipt"]["receipt_hash"] != mutation_receipt_digest:
        raise ConnectedOracleError("mutation receipt hash mismatch")
    compile_report = output["compile_report"]
    compile_receipt_digest = None
    if compile_report is not None:
        compile_receipt_digest = compile_receipt_hash(compile_report["receipt"])
    if (compile_report is None) != (bundle is None):
        raise ConnectedOracleError("compile report/opcode bundle nullability mismatch")
    bundle_digest = None
    if bundle is not None:
        bundle_digest = opcode_bundle_hash(bundle)
        if bundle["bundle_hash"] != bundle_digest:
            raise ConnectedOracleError("opcode bundle hash mismatch")
    entry = {
        "schema": "cps.connected-cache-entry",
        "schema_version": "1.0.0",
        "key": cache_key(request_digest, manifest_digest),
        "logical_output": deepcopy(output),
        "logical_output_hash": output_digest,
        "mutation_receipt_hash": mutation_receipt_digest,
        "compile_receipt_hash": compile_receipt_digest,
        "opcode_stream_bundle": deepcopy(bundle),
        "opcode_stream_bundle_hash": bundle_digest,
    }
    entry["entry_hash"] = cache_entry_hash(entry)
    return entry


def validate_cache_entry(
    entry: dict[str, Any], request: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    expected_key = cache_key(
        connected_request_hash(request), executor_manifest_digest(request["executor_manifest"])
    )
    if entry.get("key") != expected_key:
        raise ConnectedOracleError("requested_key")
    if entry.get("entry_hash") != cache_entry_hash(entry):
        raise ConnectedOracleError("entry_hash")
    output = entry["logical_output"]
    if entry.get("logical_output_hash") != logical_output_hash(output):
        raise ConnectedOracleError("logical_output_hash")
    if output.get("logical_output_hash") != entry["logical_output_hash"]:
        raise ConnectedOracleError("logical_output_hash")
    expected_mutation_receipt = mutation_receipt_hash(output["mutation_receipt"])
    if output["mutation_receipt"].get("receipt_hash") != expected_mutation_receipt:
        raise ConnectedOracleError("receipt_hash")
    if entry.get("mutation_receipt_hash") != expected_mutation_receipt:
        raise ConnectedOracleError("receipt_hash")
    report = output["compile_report"]
    bundle = entry["opcode_stream_bundle"]
    if (report is None) != (bundle is None):
        raise ConnectedOracleError("cross_binding")
    if report is None:
        if entry["compile_receipt_hash"] is not None or entry["opcode_stream_bundle_hash"] is not None:
            raise ConnectedOracleError("cross_binding")
    else:
        expected_receipt = compile_receipt_hash(report["receipt"])
        if entry["compile_receipt_hash"] != expected_receipt:
            raise ConnectedOracleError("receipt_hash")
        expected_bundle = opcode_bundle_hash(bundle)
        if bundle["bundle_hash"] != expected_bundle or entry["opcode_stream_bundle_hash"] != expected_bundle:
            raise ConnectedOracleError("opcode_hash")
        receipt = report["receipt"]
        if bundle["root"]["stream_hash"] != receipt["opcode_stream_hash"]:
            raise ConnectedOracleError("opcode_hash")
        if len(bundle["children"]) != len(receipt["children"]):
            raise ConnectedOracleError("opcode_hash")
        for bundled, child in zip(bundle["children"], receipt["children"], strict=True):
            if (bundled["kind"], bundled["query_id"]) != (child["kind"], child["query_id"]):
                raise ConnectedOracleError("opcode_hash")
            if bundled["stream"]["input_hash"] != child["input_hash"]:
                raise ConnectedOracleError("opcode_hash")
            if bundled["stream"]["stream_hash"] != child["opcode_stream_hash"]:
                raise ConnectedOracleError("opcode_hash")
    return deepcopy(output), deepcopy(bundle)


def replay_cache_mode(
    mode: str,
    request: dict[str, Any],
    cold_output: dict[str, Any],
    cold_bundle: dict[str, Any] | None,
    entry: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, int]]:
    """Return the authoritative projection for a single isolated cache cell."""
    if mode == "cold":
        if entry is not None:
            raise ConnectedOracleError("cold namespace must be empty")
        return deepcopy(cold_output), deepcopy(cold_bundle), {
            "lookups": 1, "hits": 0, "misses": 1, "corrupt_entries": 0, "recomputations": 1
        }
    if entry is None:
        raise ConnectedOracleError("preseeded cache entry required")
    if mode == "hit":
        output, bundle = validate_cache_entry(entry, request)
        return output, bundle, {
            "lookups": 1, "hits": 1, "misses": 0, "corrupt_entries": 0, "recomputations": 0
        }
    if mode == "corrupt":
        try:
            validate_cache_entry(entry, request)
        except (ConnectedOracleError, KeyError, TypeError, ValueError):
            return deepcopy(cold_output), deepcopy(cold_bundle), {
                "lookups": 1, "hits": 0, "misses": 0, "corrupt_entries": 1, "recomputations": 1
            }
        raise ConnectedOracleError("corrupt fixture unexpectedly validated")
    raise ConnectedOracleError("unknown cache mode")


def json_pointer_replace(value: Any, pointer: str, replacement: Any) -> Any:
    if not pointer.startswith("/"):
        raise ConnectedOracleError("JSON pointer must be non-root")
    result = deepcopy(value)
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
    parent = result
    for part in parts[:-1]:
        parent = parent[int(part)] if isinstance(parent, list) else parent[part]
    leaf = parts[-1]
    if isinstance(parent, list):
        parent[int(leaf)] = deepcopy(replacement)
    else:
        if leaf not in parent:
            raise ConnectedOracleError("JSON pointer does not exist")
        parent[leaf] = deepcopy(replacement)
    return result


def semantic_input_hash(case_pairs: list[dict[str, str]], ceiling: int) -> str:
    core = {"cases": case_pairs, "global_compile_logical_ceiling": ceiling}
    return artifact_hash("cps.connected-runner-input/v1", core)


def semantic_runner_request_hash(request: dict[str, Any]) -> str:
    core = {key: deepcopy(value) for key, value in request.items() if key != "execution"}
    return artifact_hash("cps.connected-runner-semantic-request/v1", core)


def runner_result_hash(result: dict[str, Any]) -> str:
    return artifact_hash("cps.connected-runner-result/v1", result, omit="result_hash")


def build_runner_result(
    request: dict[str, Any], outputs: list[tuple[str, dict[str, Any]]]
) -> dict[str, Any]:
    ceiling = request["global_compile_logical_ceiling"]
    used = 0
    published: list[dict[str, Any]] = []
    failure = None
    for ordinal, (case_id, output) in enumerate(outputs):
        report = output["compile_report"]
        charge = 0 if report is None else report["receipt"]["usage"]["total_logical_units"]
        if used + charge > ceiling:
            failure = {
                "task_ordinal": ordinal,
                "case_id": case_id,
                "code": "RUN_COMPILE_BUDGET_EXCEEDED",
                "stage": "publish_budget",
                "counter": "total_logical_units",
                "requested": charge,
                "used": used,
                "ceiling": ceiling,
            }
            break
        used += charge
        published.append({
            "task_ordinal": ordinal,
            "case_id": case_id,
            "logical_output_hash": output["logical_output_hash"],
            "logical_output": deepcopy(output),
        })
    result = {
        "schema": "cps.connected-runner-result",
        "schema_version": "1.0.0",
        "semantic_request_hash": semantic_runner_request_hash(request),
        "status": "failure" if failure else "success",
        "published_results": published,
        "failure": failure,
        "global_budget_used": used,
    }
    result["result_hash"] = runner_result_hash(result)
    return result
