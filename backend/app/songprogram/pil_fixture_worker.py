"""Fresh-process worker for one authenticated PIL oracle case."""

from __future__ import annotations

import json
import sys

from .perceptual import canonical_report_bytes
from .pil_fixture_suite import execute_pil_oracle_case


def main() -> None:
    case = json.loads(sys.stdin.buffer.read())
    report = execute_pil_oracle_case(case)
    sys.stdout.buffer.write(canonical_report_bytes(report))


if __name__ == "__main__":
    main()
