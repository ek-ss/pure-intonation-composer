from __future__ import annotations

import json
import sys

from .search_oracle import action_id, canonical_bytes, choose, draw, seal_record, stream_key


def main() -> None:
    request = json.loads(sys.stdin.buffer.read())
    if request["operation"] == "stream":
        key = stream_key(request["root_seed"], request["cohort_index"], request["path"])
        value = draw(key, request["counter"])
        index, selected = choose(request["table"], value)
        response = {"stream_key": key.hex(), "draw_u64": value, "choice_index": index, "value": selected}
    elif request["operation"] == "action_id":
        response = {"action_id": action_id(request["run_hash"], request["round"], request["phase"], request["candidate"])}
    elif request["operation"] == "seal_record":
        response = seal_record(request["record"])
    else:
        raise ValueError("unknown operation")
    sys.stdout.buffer.write(canonical_bytes(response))


if __name__ == "__main__":
    main()
