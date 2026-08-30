from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import ROUND_FLOOR, getcontext

from songprogram_conformance.protocol import canonical_bytes, run_case


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one SongProgram conformance fixture")
    parser.add_argument("--case", default="minimal_direct_note")
    parser.add_argument("--cache", choices=("cold", "hit", "corrupt"), default="cold")
    args = parser.parse_args()
    if not sys.stdin.isatty():
        payload = sys.stdin.buffer.read()
        if payload:
            request = json.loads(payload)
            if set(request) != {"operation", "case", "cache"} or request["operation"] != "run_fixture":
                raise ValueError("stdin request must be a closed run_fixture object")
            args.case, args.cache = request["case"], request["cache"]
    if os.environ.get("CPS_CALLER_DECIMAL") == "low_floor":
        getcontext().prec = 6
        getcontext().rounding = ROUND_FLOOR
    sys.stdout.buffer.write(canonical_bytes(run_case(args.case, args.cache)) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
