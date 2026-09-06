"""Independent GEN0-B path and chord-member binding fixture oracle.

This module intentionally imports no production ``app.songprogram`` code.
"""

from __future__ import annotations

import hashlib
from itertools import combinations, permutations
from typing import Any

from .canonical import canonical_bytes
from .reference import parse_ratio, ratio_mc


def artifact_hash(domain: str, value: Any) -> str:
    payload = domain.encode("utf-8") + b"\0" + canonical_bytes(value) + b"\n"
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def progression_result(query: dict[str, Any]) -> dict[str, Any]:
    """Exhaustively enumerate matchings and layered paths."""
    equave_mc = ratio_mc(parse_ratio(query["domain_equave"]))
    layers = query["occurrences"]
    paths: list[tuple[tuple[Any, ...], list[dict[str, Any]], list[list[int]]]] = []
    for core in layers[0]["candidate_cores"]:
        paths.append(((0, 0, 0, 0, 0, 0, 0, 0,
                       core["local_pair_rms_millicents"], core["local_pair_max_millicents"],
                       core["local_complexity"], ((layers[0]["id"], core["core_hash"], None),)), [core], []))
    for layer_index, occurrence in enumerate(layers[1:], 1):
        advanced = []
        for right in occurrence["candidate_cores"]:
            options = []
            for score, selected, keys in paths:
                left = selected[-1]
                nl, nr = len(left["voices"]), len(right["voices"])
                left_small = nl <= nr
                matchings = []
                for targets in permutations(range(nr if left_small else nl), min(nl, nr)):
                    pairs = [(i, target) if left_small else (target, i) for i, target in enumerate(targets)]
                    ua = [i for i in range(nl) if i not in {p[0] for p in pairs}]
                    ub = [i for i in range(nr) if i not in {p[1] for p in pairs}]
                    key = [0 if left_small else 1, len(pairs), *[v for p in pairs for v in p], 8, *ua, 8, *ub]
                    motion = [abs(right["voices"][b]["ratio_millicents"] - left["voices"][a]["ratio_millicents"]) for a, b in pairs]
                    lost = sum(left["voices"][a]["exact_ratio"] != right["voices"][b]["exact_ratio"] for a, b in pairs)
                    crossing = sum((a < c) != (b < d) for (a, b), (c, d) in combinations(pairs, 2))
                    drift = 0
                    for a, b in pairs:
                        av, bv = left["voices"][a], right["voices"][b]
                        if av["exact_ratio"] == bv["exact_ratio"] or av["target_ordinal"] != bv["target_ordinal"]:
                            continue
                        delta = bv["ratio_millicents"] - av["ratio_millicents"]
                        q = delta // equave_mc
                        phase = min((delta-q*equave_mc, delta-(q+1)*equave_mc), key=lambda x: (abs(x), x))
                        drift += abs(delta-phase)
                    l1 = sum(sum(abs(x-y) for x, y in zip(left["voices"][a]["absolute_vector"], right["voices"][b]["absolute_vector"])) + abs(left["voices"][a]["equave_exponent"]-right["voices"][b]["equave_exponent"]) for a, b in pairs)
                    bass = abs(min(v["ratio_millicents"] for v in right["voices"])-min(v["ratio_millicents"] for v in left["voices"]))
                    matchings.append(((abs(nl-nr), lost, crossing, sum(motion), max(motion, default=0), bass, drift, l1, key), key))
                edge, key = min(matchings, key=lambda item: item[0])
                if edge[4] > query["maximum_voice_motion_millicents"] or (query["crossing_policy"] == "forbid" and edge[2]):
                    continue
                combined = (*[score[i]+edge[i] for i in range(4)], max(score[4], edge[4]),
                            *[score[i]+edge[i] for i in range(5, 8)],
                            score[8]+right["local_pair_rms_millicents"],
                            score[9]+right["local_pair_max_millicents"],
                            score[10]+right["local_complexity"],
                            score[11]+((occurrence["id"], right["core_hash"], key),))
                options.append((combined, selected+[right], keys+[key]))
            if options:
                advanced.append(min(options, key=lambda item: item[0]))
        paths = advanced
    if not paths:
        raise ValueError("PROGRESSION_NO_PATH")
    score, selected, keys = min(paths, key=lambda item: item[0])
    result = {"schema":"cps.progression-result","schema_version":"1.1.0","search_completeness":"exact",
              "selected_core_hashes":[c["core_hash"] for c in selected],"edge_matching_keys":keys,
              "score_prefix":list(score[:11]),"canonical_path_key":[{"occurrence_id":a,"resolved_core_hash":b,"matching_key":c} for a,b,c in score[11]]}
    result["path_hash"] = "sha256:" + hashlib.sha256(canonical_bytes(result)).hexdigest()
    return result


def bind_chord_members(records: list[dict[str, Any]], occurrences: list[dict[str, Any]], chords: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for record in records:
        end = record["start_tick"] + record["duration_ticks"]
        active = [o for o in occurrences if o["section_id"] == record["section_id"] and o["start_tick"] <= record["start_tick"] and end <= o["start_tick"] + o["duration_ticks"]]
        if len(active) != 1:
            raise ValueError("MELODY_HARMONY_CONFLICT")
        chord = chords[active[0]["resolved_chord_id"]]
        try:
            shape = chord["target_voice_ordinals"].index(record["member"])
        except ValueError as error:
            raise ValueError("MELODY_HARMONY_CONFLICT") from error
        output.append({**record, "active": active[0], "chord": chord, "shape_voice_ordinal": shape})
    return output
