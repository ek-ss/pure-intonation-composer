"""Summarize blinded G2 listening responses without inventing pass thresholds."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.songprogram.composition_calibration import build_blind_assignment  # noqa: E402
from app.songprogram.search import canonical_bytes  # noqa: E402


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _hash(domain: str, value: dict, member: str) -> str:
    return "sha256:" + hashlib.sha256(
        domain.encode() + b"\0" + canonical_bytes({k: v for k, v in value.items() if k != member})
    ).hexdigest()


def summarize(root: Path) -> dict:
    split = _load(root / "private_lineage_split.json")
    if split.get("split_hash") != _hash("cps.composition-calibration-split/v1", split, "split_hash"):
        raise ValueError("invalid private lineage split hash")
    answers_by_candidate = defaultdict(lambda: defaultdict(Counter))
    technical_failures = Counter()
    listeners_by_partition = {}
    for partition in ("calibration", "holdout"):
        assignment = _load(root / f"blind_{partition}.json")
        if (assignment.get("source_split_hash") != split["split_hash"]
                or assignment.get("partition") != partition
                or assignment.get("assignment_hash") != _hash(
                    "cps.composition-blind-assignment/v1", assignment, "assignment_hash"
                )):
            raise ValueError(f"invalid blind assignment: {partition}")
        sources = {row["blind_id"]: row for row in assignment["assignments"]}
        if len(sources) != len(assignment["assignments"]):
            raise ValueError("duplicate blind ID")
        expected = build_blind_assignment(
            split, partition=partition, assignment_seed=assignment["assignment_seed"]
        )
        private = {
            "blind_" + hashlib.sha256(
                b"cps.g2-blind-id/v1\0" + assignment["assignment_seed"].to_bytes(8, "big")
                + row["candidate_id"].encode()
            ).hexdigest()[:16]: row
            for row in split["assignments"] if row["partition"] == partition
        }
        candidate_by_blind = {}
        for original, exposed in zip(expected["assignments"], assignment["assignments"], strict=True):
            if (original["blind_id"] != exposed["blind_id"]
                    or original["ordinal"] != exposed["ordinal"]
                    or original["audio_hash"] != exposed["audio_hash"]
                    or Path(exposed["audio_path"]).name != f"{exposed['blind_id']}.wav"):
                raise ValueError("blind assignment differs from private split")
            if (original["blind_id"] not in private
                    or private[original["blind_id"]]["audio_path"] != original["audio_path"]):
                raise ValueError("blind ID has no matching private candidate")
            candidate_by_blind[original["blind_id"]] = private[original["blind_id"]]["candidate_id"]
        listeners = set()
        for path in sorted((root / "responses" / partition).glob("*.json")):
            response = _load(path)
            if (response.get("assignment_hash") != assignment["assignment_hash"]
                    or response.get("partition") != partition
                    or response.get("schema") != "cps.composition-blind-response"
                    or response.get("response_hash") != _hash(
                        "cps.composition-blind-response/v1", response, "response_hash"
                    )):
                raise ValueError(f"invalid G2 response: {path}")
            listener = response.get("listener_id")
            if not isinstance(listener, str) or listener in listeners:
                raise ValueError(f"duplicate or invalid listener for {partition}: {listener}")
            listeners.add(listener)
            item_ids = [item["blind_id"] for item in response["responses"]]
            if len(item_ids) != len(sources) or set(item_ids) != set(sources):
                raise ValueError(f"incomplete G2 response: {path}")
            for item in response["responses"]:
                candidate_id = candidate_by_blind[item["blind_id"]]
                if item["technical_failure"]:
                    if item["answers"] is not None:
                        raise ValueError(f"technical failure has answers: {path}")
                    technical_failures[candidate_id] += 1
                    continue
                if set(item["answers"]) != set(assignment["questions"]):
                    raise ValueError(f"unexpected G2 questions: {path}")
                for question, answer in item["answers"].items():
                    if answer not in assignment["response_enum"]:
                        raise ValueError(f"unexpected G2 answer: {path}")
                    answers_by_candidate[candidate_id][question][answer] += 1
        listeners_by_partition[partition] = len(listeners)
    rows = []
    for candidate in split["assignments"]:
        candidate_id = candidate["candidate_id"]
        questions = {
            question: {answer: answers_by_candidate[candidate_id][question][answer]
                       for answer in ("yes", "uncertain", "no")}
            for question in _load(root / f"blind_{candidate['partition']}.json")["questions"]
        }
        valid_count = sum(questions[next(iter(questions))].values()) if questions else 0
        rows.append({"candidate_id": candidate_id, "cohort": candidate["cohort"],
                     "partition": candidate["partition"], "valid_listeners": valid_count,
                     "technical_failures": technical_failures[candidate_id],
                     "at_least_three_listeners": valid_count >= 3, "questions": questions})
    result = {"schema": "cps.generated-song-g2-summary", "schema_version": "1.0.0",
              "non_authoritative": True, "listeners_by_partition": listeners_by_partition,
              "rows": rows}
    result["report_hash"] = _hash("cps.generated-song-g2-summary/v1", result, "report_hash")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    report = summarize(args.root)
    (args.root / "g2_summary.json").write_bytes(canonical_bytes(report))
    print(json.dumps({"listeners_by_partition": report["listeners_by_partition"],
                      "report_hash": report["report_hash"]}, sort_keys=True))


if __name__ == "__main__":
    main()
